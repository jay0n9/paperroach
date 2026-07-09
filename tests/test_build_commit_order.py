import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kb import pipeline
from kb.config import Config
from kb.models import Chunk, PaperAnalysis, PaperClassification, PaperMetadata, doc_id_for


class FakeClient:
    def __init__(self, config):
        self.config = config

    def ping(self):
        return None

    def unload_embed(self):
        return None

    def unload_llm(self):
        return None

    def embed(self, texts):
        return [[0.0] * self.config.embed_dim for _ in texts]


class BuildCommitOrderTests(unittest.TestCase):
    def _patch_build_dependencies(self, store_cls, write_note, write_concepts=None):
        concept_patch = (
            patch.object(
                pipeline.knowledge,
                "write_concept_notes",
                side_effect=write_concepts,
            )
            if write_concepts
            else patch.object(pipeline.knowledge, "write_concept_notes", return_value=[])
        )
        return (
            patch.object(pipeline, "OllamaClient", FakeClient),
            patch.object(pipeline, "KBStore", store_cls),
            patch.object(pipeline.ingest_mod, "ingest", return_value="# Paper\n\nBody"),
            patch.object(
                pipeline,
                "extract_metadata",
                return_value=PaperMetadata(
                    title="Commit Order Paper",
                    year=2024,
                    summary="A short summary.",
                ),
            ),
            patch.object(pipeline, "extract_analysis", return_value=PaperAnalysis()),
            patch.object(
                pipeline,
                "classify_paper",
                return_value=PaperClassification(
                    primary_domain="HCI",
                    subdomain="Health & Wellbeing",
                ),
            ),
            patch.object(
                pipeline,
                "chunk_markdown",
                return_value=[Chunk(chunk_index=0, header="", text="Body")],
            ),
            patch.object(pipeline.obsidian, "write_generated_note", side_effect=write_note),
            concept_patch,
        )

    def _build_quietly(self, source: Path, config: Config, patches):
        with ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            with redirect_stdout(StringIO()):
                return pipeline.build([source], config)

    def test_pdf_note_write_failure_does_not_commit_store_or_hash_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            config = Config(vault_path=root / "vault", kb_dir=".kb")
            stores = []

            class Store:
                def __init__(self, _config):
                    self.upserts = []
                    stores.append(self)

                def all_docs(self, columns=None):
                    return []

                def related_for_vector(self, query_vector, exclude_doc_id, k):
                    return []

                def upsert_document(self, doc, chunk_vectors, summary_vector):
                    self.upserts.append(doc.doc_id)

                def optimize(self):
                    return None

                def counts(self):
                    return len(self.upserts), 0

            patches = self._patch_build_dependencies(
                Store, OSError("cannot write generated note")
            )
            result = self._build_quietly(source, config, patches)

            self.assertEqual(result["processed"], 0)
            self.assertEqual(result["succeeded"], [])
            self.assertEqual(stores[0].upserts, [])
            ledger_path = config.kb_path / "content_hashes.json"
            if ledger_path.exists():
                self.assertEqual(json.loads(ledger_path.read_text(encoding="utf-8")), {})

    def test_pdf_note_is_written_before_store_and_hash_ledger_commit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            config = Config(vault_path=root / "vault", kb_dir=".kb")
            order = []

            class Store:
                def __init__(self, _config):
                    self.upserts = []

                def all_docs(self, columns=None):
                    return []

                def related_for_vector(self, query_vector, exclude_doc_id, k):
                    return []

                def upsert_document(self, doc, chunk_vectors, summary_vector):
                    order.append("store")
                    self.upserts.append(doc.doc_id)

                def optimize(self):
                    return None

                def counts(self):
                    return len(self.upserts), 0

            def write_note(doc, related_links, _config):
                order.append("write")
                assert doc.note_path is not None
                doc.note_path.parent.mkdir(parents=True, exist_ok=True)
                doc.note_path.write_text("note", encoding="utf-8")
                return doc.note_path

            patches = self._patch_build_dependencies(Store, write_note)
            result = self._build_quietly(source, config, patches)

            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["succeeded"], [doc_id_for(source)])
            self.assertEqual(order[:2], ["write", "store"])
            ledger = json.loads(
                (config.kb_path / "content_hashes.json").read_text(encoding="utf-8")
            )
            self.assertEqual(list(ledger.values()), [doc_id_for(source)])

    def test_store_failure_after_note_write_does_not_commit_hash_or_concepts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            config = Config(vault_path=root / "vault", kb_dir=".kb")
            order = []
            concept_calls = []
            old_note = config.references_path / "Old Title (2024).md"
            old_note.parent.mkdir(parents=True, exist_ok=True)
            old_note.write_text(
                "---\nkb-generated: true\n---\n# Old Title\n",
                encoding="utf-8",
            )
            doc_id = doc_id_for(source)

            class Store:
                def __init__(self, _config):
                    pass

                def all_docs(self, columns=None):
                    return [{"doc_id": doc_id, "note_path": str(old_note)}]

                def related_for_vector(self, query_vector, exclude_doc_id, k):
                    return []

                def upsert_document(self, doc, chunk_vectors, summary_vector):
                    order.append("store")
                    raise RuntimeError("db unavailable")

                def optimize(self):
                    return None

                def counts(self):
                    return 0, 0

            def write_note(doc, related_links, _config):
                order.append("write")
                assert doc.note_path is not None
                doc.note_path.parent.mkdir(parents=True, exist_ok=True)
                doc.note_path.write_text("note", encoding="utf-8")
                return doc.note_path

            def write_concepts(doc, _config):
                concept_calls.append(doc.doc_id)
                return []

            patches = self._patch_build_dependencies(Store, write_note, write_concepts)
            result = self._build_quietly(source, config, patches)

            self.assertEqual(result["processed"], 0)
            self.assertEqual(result["succeeded"], [])
            self.assertEqual(order, ["write", "store"])
            self.assertEqual(concept_calls, [])
            self.assertTrue(old_note.exists())
            ledger_path = config.kb_path / "content_hashes.json"
            if ledger_path.exists():
                self.assertEqual(json.loads(ledger_path.read_text(encoding="utf-8")), {})


if __name__ == "__main__":
    unittest.main()
