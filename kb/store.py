"""Stage ⑤ — LanceDB vector store (file-based, under <vault>/.kb).

Two tables:
    chunks : body chunks + vector        -> RAG retrieval
    docs   : one summary vector per doc  -> related-literature linking

Cosine distance is used throughout; embeddings are already L2-normalised by
the Ollama client, so cosine and inner-product rank identically.
"""
from __future__ import annotations

from pathlib import Path

import lancedb
import pyarrow as pa

from kb.config import Config
from kb.models import Document


def _chunks_schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("doc_id", pa.string()),
            pa.field("note_path", pa.string()),
            pa.field("title", pa.string()),
            pa.field("header", pa.string()),
            pa.field("text", pa.string()),
            pa.field("chunk_index", pa.int32()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
        ]
    )


def _docs_schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("doc_id", pa.string()),
            pa.field("title", pa.string()),
            pa.field("authors", pa.list_(pa.string())),
            pa.field("year", pa.int32()),
            pa.field("kind", pa.string()),
            pa.field("note_path", pa.string()),
            pa.field("link_target", pa.string()),
            pa.field("summary", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("vector", pa.list_(pa.float32(), dim)),
        ]
    )


def _concepts_schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("concept_id", pa.string()),
            pa.field("name", pa.string()),
            pa.field("note_path", pa.string()),
            pa.field("subject", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
        ]
    )


class KBStore:
    def __init__(self, config: Config):
        self.config = config
        config.kb_path.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(config.kb_path))
        self.chunks = self._open_or_create("chunks", _chunks_schema(config.embed_dim))
        self.docs = self._open_or_create("docs", _docs_schema(config.embed_dim))
        self.concepts = self._open_or_create(
            "concepts", _concepts_schema(config.embed_dim)
        )

    def _open_or_create(self, name: str, schema: pa.Schema):
        if name in self.db.table_names():
            table = self.db.open_table(name)
            self._check_dim(name, table)
            return table
        return self.db.create_table(name, schema=schema)

    def _check_dim(self, name: str, table) -> None:
        """Fail loudly if the stored vector width no longer matches the config.

        Without this, changing ``embed_dim``/``embed_model`` used to delete a
        document's old rows and then fail on the re-add — losing data.
        """
        try:
            field = table.schema.field("vector")
            stored = getattr(field.type, "list_size", None)
        except (KeyError, AttributeError):
            return
        if stored is not None and stored != self.config.embed_dim:
            raise RuntimeError(
                f"Table '{name}' holds {stored}-dim vectors but embed_dim is "
                f"{self.config.embed_dim}. Either restore the old embed model/"
                f"dim in kb.toml, or delete {self.config.kb_path} and rebuild."
            )

    # ── writes ──────────────────────────────────────────────────────
    def upsert_document(
        self,
        doc: Document,
        chunk_vectors: list[list[float]],
        summary_vector: list[float],
    ) -> None:
        """Replace all rows for ``doc`` in both tables (idempotent re-runs)."""
        # chunks: delete->add (the row count changes between runs, so a keyed
        # merge cannot remove stale rows). A crash between the two steps is
        # self-healing: the next build of the same file re-adds everything.
        self._delete(self.chunks, doc.doc_id)

        note_path = str(doc.note_path) if doc.note_path else ""
        chunk_rows = [
            {
                "id": f"{doc.doc_id}:{c.chunk_index}",
                "doc_id": doc.doc_id,
                "note_path": note_path,
                "title": doc.metadata.title,
                "header": c.header,
                "text": c.text,
                "chunk_index": c.chunk_index,
                "vector": vec,
            }
            for c, vec in zip(doc.chunks, chunk_vectors)
        ]
        if chunk_rows:
            self.chunks.add(chunk_rows)

        # docs: exactly one row per doc_id -> a keyed merge is a true atomic
        # upsert (no delete-then-add window).
        doc_row = {
            "doc_id": doc.doc_id,
            "title": doc.metadata.title,
            "authors": doc.metadata.authors,
            "year": doc.metadata.year,
            "kind": doc.kind,
            "note_path": note_path,
            "link_target": doc.link_target or "",
            "summary": doc.metadata.summary,
            "tags": doc.metadata.tags,
            "vector": summary_vector,
        }
        (
            self.docs.merge_insert("doc_id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute([doc_row])
        )

    @staticmethod
    def _delete(table, doc_id: str) -> None:
        # doc_id is a 12-char hex string, safe to interpolate.
        table.delete(f"doc_id = '{doc_id}'")

    # ── reads ───────────────────────────────────────────────────────
    def search_chunks(self, query_vector: list[float], k: int) -> list[dict]:
        return (
            self.chunks.search(query_vector)
            .metric("cosine")
            .limit(k)
            .to_list()
        )

    def related_for_vector(
        self, query_vector: list[float], exclude_doc_id: str, k: int
    ) -> list[dict]:
        rows = (
            self.docs.search(query_vector)
            .metric("cosine")
            .limit(k + 1)
            .to_list()
        )
        out = [r for r in rows if r["doc_id"] != exclude_doc_id]
        return out[:k]

    def all_docs(self, columns: list[str] | None = None) -> list[dict]:
        """Full scan of the docs table, pandas-free.

        Pass ``columns`` to skip the 1024-dim vectors when only metadata is
        needed (much cheaper as the library grows).
        """
        if self.docs.count_rows() == 0:
            return []
        tbl = self.docs.to_arrow()
        if columns:
            tbl = tbl.select(columns)
        return tbl.to_pylist()

    def counts(self) -> tuple[int, int]:
        return self.docs.count_rows(), self.chunks.count_rows()

    # ── maintenance ─────────────────────────────────────────────────
    def update_note_path(self, doc_id: str, note_path: str) -> None:
        """Point a document's rows at a moved note file (used by `kb refile`)."""
        for table in (self.docs, self.chunks):
            table.update(
                where=f"doc_id = '{doc_id}'", values={"note_path": note_path}
            )

    def delete_doc(self, doc_id: str) -> None:
        """Remove a document and all its chunks (used by `kb gc`)."""
        self._delete(self.chunks, doc_id)
        self._delete(self.docs, doc_id)

    def delete_concept(self, concept_id: str) -> None:
        self.concepts.delete(f"concept_id = '{concept_id}'")

    def optimize(self) -> None:
        """Compact fragments and drop old table versions.

        delete+add churn (every rebuild / watch cycle) accumulates fragments
        and versions that slow scans and grow the store on disk.
        """
        for table in (self.chunks, self.docs, self.concepts):
            try:
                table.optimize()
            except Exception:
                pass  # best-effort; never block a build on housekeeping

    # ── concepts (Knowledge Library cross-linking) ──────────────────
    def upsert_concept(self, row: dict) -> None:
        self.concepts.delete(f"concept_id = '{row['concept_id']}'")
        self.concepts.add([row])

    def indexed_concept_ids(self) -> set[str]:
        if self.concepts.count_rows() == 0:
            return set()
        return {r["concept_id"] for r in self.concepts.to_arrow().to_pylist()}

    def all_concepts(self) -> list[dict]:
        if self.concepts.count_rows() == 0:
            return []
        return self.concepts.to_arrow().to_pylist()

    def related_concepts(
        self, query_vector: list[float], exclude_id: str, k: int
    ) -> list[dict]:
        rows = (
            self.concepts.search(query_vector)
            .metric("cosine")
            .limit(k + 1)
            .to_list()
        )
        out = [r for r in rows if r["concept_id"] != exclude_id]
        return out[:k]

    def concept_count(self) -> int:
        return self.concepts.count_rows()
