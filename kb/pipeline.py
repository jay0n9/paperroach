"""Build orchestration: PASS A (ingest, then LLM) → model swap → PASS B.

    PASS A0  ingest every input → Markdown       [no Ollama model needed;
                                                  nougat gets the GPU alone]
    PASS A1  metadata → analysis → chunk          [Qwen3 8B resident]
       ⇄     unload LLM  ───────────────────────  [VRAM swap, once]
    PASS B   embed → link → write note → store     [bge-m3 resident]

The swap is the key 8GB design point: the 7GB LLM is fully evicted before the
1.2GB embedder loads (and vice versa at the start of a run), so they never
co-reside. Ingesting everything first (A0) matters for the nougat ingester:
interleaving ingest and LLM used to force a full model swap per file.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from contextlib import nullcontext
from pathlib import Path

from kb import ingest as ingest_mod
from kb import knowledge
from kb import obsidian
from kb import organize
from kb import tags as tags_mod
from kb import taxonomy
from kb import zotero
from kb.chunk import chunk_markdown
from kb.config import Config
from kb.llm import (
    classify_paper,
    classification_metadata_text,
    extract_analysis,
    extract_concepts,
    extract_metadata,
    metadata_classification,
    normalize_concept_key,
    write_concept_article,
    write_integrated_approach,
)
from kb.models import (
    Document,
    PaperAnalysis,
    PaperClassification,
    PaperMetadata,
    content_hash_for,
    doc_id_for,
)
from kb.ollama_client import OllamaClient, OllamaError
from kb.store import KBStore, table_names


def _log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe = msg.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe, flush=True)


DEFAULT_PIPELINE_LOCK_STALE_SECONDS = 12 * 60 * 60


class PipelineLockError(RuntimeError):
    """Raised when a fresh PaperRoach write lock already exists."""


class PipelineLock:
    """Atomic file lock for commands that write notes or the vector store."""

    def __init__(
        self,
        config: Config,
        owner: str,
        stale_seconds: float = DEFAULT_PIPELINE_LOCK_STALE_SECONDS,
        heartbeat_interval: float | None = None,
    ) -> None:
        self.path = config.kb_path / "pipeline.lock"
        self.owner = owner
        self.stale_seconds = stale_seconds
        self.heartbeat_interval = (
            heartbeat_interval
            if heartbeat_interval is not None
            else min(60.0, max(0.1, stale_seconds / 3.0))
        )
        self.token = f"{os.getpid()}:{time.time():.6f}:{owner}"
        self._acquired = False
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def __enter__(self) -> "PipelineLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._acquire()
        self._acquired = True
        self._start_heartbeat()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def heartbeat(self) -> None:
        """Refresh the lock mtime without exposing a partial JSON payload."""
        if not self._acquired or not self._owns_lock():
            return
        try:
            os.utime(self.path, None)
        except OSError:
            return

    def release(self) -> None:
        if not self._acquired:
            return
        self._stop_heartbeat()
        if not self._owns_lock():
            self._acquired = False
            return
        self._acquired = False
        try:
            self.path.unlink()
        except OSError:
            pass

    def _start_heartbeat(self) -> None:
        if self.heartbeat_interval <= 0:
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"paperroach-lock-{self.owner}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        self._heartbeat_thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self.heartbeat_interval):
            self.heartbeat()

    def _acquire(self) -> None:
        try:
            self._write_new_lock()
            return
        except FileExistsError:
            pass

        if not self._is_stale():
            raise PipelineLockError(self._busy_message())

        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise PipelineLockError(self._busy_message()) from exc

        try:
            self._write_new_lock()
        except FileExistsError as exc:
            raise PipelineLockError(self._busy_message()) from exc

    def _write_new_lock(self) -> None:
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(self._payload())

    def _payload(self) -> str:
        return json.dumps(
            {
                "owner": self.owner,
                "pid": os.getpid(),
                "token": self.token,
                "updated_at": time.time(),
            },
            indent=1,
        )

    def _is_stale(self) -> bool:
        try:
            return (time.time() - self.path.stat().st_mtime) >= self.stale_seconds
        except OSError:
            return False

    def _owns_lock(self) -> bool:
        return self._lock_details().get("token") == self.token

    def _lock_details(self) -> dict[str, object]:
        try:
            text = self.path.read_text(encoding="utf-8")
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _busy_message(self) -> str:
        details = self._lock_details()
        owner = details.get("owner") or "unknown"
        pid = details.get("pid") or "unknown"
        return (
            "Another PaperRoach write command appears to be running "
            f"(owner={owner}, pid={pid}, lock={self.path}). "
            "Stop that process first, or delete the lock file if it is stale."
        )


# --------------------------------------------------------------------------- #
#  Input discovery
# --------------------------------------------------------------------------- #
def collect_inputs(paths: list[Path], config: Config, recursive: bool) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    kb = config.kb_path.resolve()

    def add(p: Path) -> None:
        p = p.resolve()
        if p in seen:
            return
        if not p.is_file():
            return
        if p.suffix.lower() not in ingest_mod.SUPPORTED_SUFFIXES:
            return
        # Never re-ingest our own output, the DB, or anything under .kb.
        if _is_relative_to(p, kb):
            return
        if p.suffix.lower() in ingest_mod.NOTE_SUFFIXES and obsidian.is_generated_note(p):
            return
        seen.add(p)
        found.append(p)

    for raw in paths:
        path = raw.expanduser()
        if path.is_dir():
            files = path.rglob("*") if recursive else path.iterdir()
            for f in sorted(files):
                add(f)
        elif path.is_file():
            add(path)
        else:
            _log(f"  ! skipping (not found): {path}")
    return found


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base)
        return True
    except ValueError:
        return False


def _cleanup_orphan(old_path: str, new_path: Path | None) -> None:
    """Remove a previously-generated note whose filename changed this run.

    Only ever deletes a file this pipeline produced (``kb-generated``), so a
    user note can never be removed even if a title collides. Anything the
    user wrote under '## My Notes' is carried over to the new note first.
    """
    if not old_path or new_path is None:
        return
    old = Path(old_path)
    if old == new_path or not old.exists():
        return
    if obsidian.is_generated_note(old):
        my_notes = obsidian.extract_my_notes(old)
        if my_notes and new_path.exists():
            obsidian.inject_my_notes(new_path, my_notes)
        try:
            old.unlink()
            _log(f"      · removed stale renamed note: {old.name}")
        except OSError:
            pass


# --------------------------------------------------------------------------- #
#  Content-hash ledger (same PDF under two paths → build once)
# --------------------------------------------------------------------------- #
def _hash_ledger_path(config: Config) -> Path:
    return config.kb_path / "content_hashes.json"


def _load_hash_ledger(config: Config) -> dict[str, str]:
    try:
        with open(_hash_ledger_path(config), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_hash_ledger(config: Config, ledger: dict[str, str]) -> None:
    path = _hash_ledger_path(config)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        pass


def _record_content_hash(ledger: dict[str, str], content_hash: str, doc_id: str) -> None:
    """Record the current bytes for a document and retire its stale hashes.

    A document id is path-based, so rebuilding a file after its contents change
    must not leave the former bytes marked as already indexed elsewhere.
    """
    stale = [key for key, value in ledger.items() if value == doc_id and key != content_hash]
    for key in stale:
        del ledger[key]
    ledger[content_hash] = doc_id


# --------------------------------------------------------------------------- #
#  Build
# --------------------------------------------------------------------------- #
def build(paths: list[Path], config: Config, recursive: bool = False) -> dict:
    config.ensure_dirs()
    inputs = collect_inputs(paths, config, recursive)
    if not inputs:
        _log("No PDF/Markdown inputs found.")
        return {"processed": 0, "succeeded": []}

    client = OllamaClient(config)
    # Fail fast if the server is down — before any expensive PDF parsing.
    try:
        client.ping()
    except OllamaError as exc:
        _log(f"  ! {exc}")
        return {"processed": 0, "succeeded": []}

    store = KBStore(config)  # opened early: schema/dim mismatches fail here

    # Drop inputs whose *content* is already in the library under another
    # path (e.g. the same PDF attached twice in Zotero).
    ledger = _load_hash_ledger(config)
    known_ids = {r["doc_id"] for r in store.all_docs(columns=["doc_id"])}
    inputs, hash_by_id, dup_ids = _dedupe_by_content(inputs, ledger, known_ids)
    if not inputs:
        _log("All inputs are duplicates of already-ingested documents.")
        return {"processed": 0, "succeeded": [], "skipped_duplicates": dup_ids}

    # ── PASS A0 ── ingest everything first ──────────────────────────
    # No Ollama model is needed here, and the nougat ingester needs the GPU
    # to itself — interleaving ingest with the LLM would swap models per file.
    _log(f"PASS A0 · ingest · {len(inputs)} input(s)")
    ingested: list[tuple[Path, str, str]] = []  # (path, kind, markdown)
    for i, path in enumerate(inputs, 1):
        _log(f"  [{i}/{len(inputs)}] {path.name}")
        try:
            kind = ingest_mod.kind_of(path)
            markdown = ingest_mod.ingest(path, config)
            ingested.append((path, kind, markdown))
        except Exception as exc:  # one bad file shouldn't sink the batch
            _log(f"      ! ingest failed: {exc}")
    if not ingested:
        _log("Nothing ingested successfully.")
        return {"processed": 0, "succeeded": []}

    # ── PASS A1 ── LLM resident ─────────────────────────────────────
    _log(f"PASS A1 · LLM ({config.llm_model}) · {len(ingested)} document(s)")
    client.unload_embed()  # a resident embedder would co-reside on 8GB
    known_subjects = sorted(set(knowledge.list_subjects(config)) | set(taxonomy.domain_names()))
    tag_registry = tags_mod.load_registry(config)
    docs: list[Document] = []
    for i, (path, kind, markdown) in enumerate(ingested, 1):
        _log(f"  [{i}/{len(ingested)}] {path.name}")
        try:
            _log("      · extracting metadata …")
            metadata = extract_metadata(
                client, markdown, path, kind, config,
                known_tags=list(tag_registry),
            )
            metadata = zotero.enrich(metadata, path, config)
            # Fold the tags onto the controlled vocabulary (aliases and
            # spelling variants collapse); document any genuinely new ones
            # in the vault's Tag Registry so it never drifts.
            metadata.tags = tags_mod.canonicalize(metadata.tags, tag_registry)
            new_count = tags_mod.register_new(config, tag_registry, metadata.tags)
            if new_count:
                _log(f"      · {new_count} new tag(s) added to the Tag Registry")
            meta_domain, meta_subdomain = metadata_classification(
                metadata, known_subjects
            )
            if meta_domain and not metadata.primary_domain:
                metadata.primary_domain = meta_domain
            if meta_subdomain and not metadata.subdomain:
                metadata.subdomain = meta_subdomain
            if metadata.subdomain:
                _log(f"      · metadata subdomain: {metadata.subdomain}")
            _log("      · analysing paper …")
            try:
                analysis = extract_analysis(client, markdown, metadata, config)
            except Exception as exc:
                _log(f"      · analysis failed ({exc}); writing note without it")
                analysis = PaperAnalysis()
            classification = PaperClassification()
            if kind == "pdf":
                _log("      · classifying paper domain …")
                try:
                    classification = classify_paper(
                        client, markdown, metadata, analysis, config, known_subjects
                    )
                except Exception as exc:
                    classification = _fallback_paper_classification(
                        metadata, analysis, known_subjects
                    )
                    _log(
                        "      · domain classification failed "
                        f"({exc}); fallback={classification.primary_domain or 'none'}"
                    )
                if classification.primary_domain:
                    _log(f"      · primary domain: {classification.primary_domain}")
                if classification.subdomain:
                    _log(f"      · subdomain: {classification.subdomain}")
            if config.create_concept_notes and analysis.concepts:
                _log("      · distilling concept notes …")
                try:
                    ce = extract_concepts(
                        client,
                        markdown,
                        metadata,
                        [c["name"] for c in analysis.concepts],
                        known_subjects,
                        config,
                    )
                    analysis.subject = ce["subject"]
                    # Match on normalised names; if the LLM returned exactly
                    # one entry per requested concept, fall back to matching
                    # by position for any stragglers.
                    entries = list(ce["concepts"].values())
                    by_index_ok = len(entries) == len(analysis.concepts)
                    missed: list[str] = []
                    for idx, c in enumerate(analysis.concepts):
                        info = ce["concepts"].get(normalize_concept_key(c["name"]))
                        if info is None and by_index_ok:
                            info = entries[idx]
                        if info:
                            c["explanation"] = info["explanation"]
                            c["why_it_matters"] = info["why_it_matters"]
                            c["tags"] = info.get("tags") or []
                            c["parent"] = info.get("parent", "")
                        else:
                            missed.append(c["name"])
                    if missed:
                        _log(
                            "      ! no distilled detail for concept(s): "
                            + ", ".join(missed)
                        )
                except Exception as exc:
                    _log(f"      · concept distillation failed ({exc}); skipping")
                _log("      · writing wiki articles …")
                # Include a slice of the raw markdown so real equations (e.g.
                # from the nougat ingester) are available to copy verbatim.
                ctx = (
                    (analysis.tl_dr or "")
                    + "\n\n"
                    + (analysis.approach or "")
                    + "\n\nSource excerpt (reuse any relevant equations verbatim):\n"
                    + markdown[:4000]
                ).strip()
                for c in analysis.concepts:
                    try:
                        c["article"] = write_concept_article(
                            client, c["name"], ctx, config
                        )
                    except Exception:
                        c["article"] = ""
            equations = _extract_equations(markdown)
            # Weave the real equations into the Approach prose (LLM resident now).
            if equations and analysis.approach:
                try:
                    _log("      · integrating equations into the methodology …")
                    analysis.approach = write_integrated_approach(
                        client, metadata.title, analysis.approach, equations, config
                    )
                    equations_integrated = True
                except Exception as exc:
                    _log(f"      · equation integration failed ({exc})")
                    equations_integrated = False
            else:
                equations_integrated = False
            chunks = chunk_markdown(markdown, config)
            doc = Document(
                doc_id=doc_id_for(path),
                source_path=path,
                kind=kind,
                markdown=markdown,
                metadata=metadata,
                chunks=chunks,
                analysis=analysis,
                classification=classification,
                equations=equations,
                equations_integrated=equations_integrated,
            )
            obsidian.assign_note_location(doc, config)
            _log(f"      · '{metadata.title}' — {len(chunks)} chunk(s)")
            docs.append(doc)
        except Exception as exc:  # one bad file shouldn't sink the batch
            _log(f"      ! failed: {exc}")

    if not docs:
        _log("Nothing analysed successfully.")
        return {"processed": 0, "succeeded": []}

    # ── SWAP ── evict LLM before the embedder loads ─────────────────
    _log("⇄  swapping models (unloading LLM, loading embedder) …")
    client.unload_llm()

    # ── PASS B ── embedder resident ─────────────────────────────────
    _log(f"PASS B · embeddings ({config.embed_model})")
    # Remember where each doc's note lived *before* this run overwrites the
    # docs table, so a renamed generated note can have its stale file removed.
    old_note_paths = {
        r["doc_id"]: r.get("note_path", "")
        for r in store.all_docs(columns=["doc_id", "note_path"])
    }
    embedded: list[tuple[Document, list[list[float]], list[float]]] = []
    for i, doc in enumerate(docs, 1):
        _log(f"  [{i}/{len(docs)}] embedding {doc.metadata.title}")
        try:
            # One request for chunks + summary (the last vector is the summary).
            summary_text = doc.metadata.summary or doc.metadata.title
            vectors = client.embed([c.text for c in doc.chunks] + [summary_text])
            chunk_vectors, summary_vector = vectors[:-1], vectors[-1]
            doc.summary_vector = summary_vector
            embedded.append((doc, chunk_vectors, summary_vector))
        except Exception as exc:
            # One transient failure must not discard the whole batch's PASS A
            # work — skip this document; a later run picks it up again.
            _log(f"      ! embedding failed: {exc}")
    if not embedded:
        _log("No document could be embedded.")
        return {"processed": 0, "succeeded": []}

    # ── ⑥ related-literature linking ────────────────────────────────
    _log("  linking related literature …")
    for doc, _chunk_vectors, _summary_vector in embedded:
        related = store.related_for_vector(
            doc.summary_vector,
            exclude_doc_id=doc.doc_id,
            k=config.related_top_k,
        )
        doc.related = [r["link_target"] for r in related if r.get("link_target")]

    # ── ⑦ write notes ───────────────────────────────────────────────
    _log("  writing notes …")
    written = 0
    concept_paths: list[Path] = []
    stored: list[Document] = []
    for doc, chunk_vectors, summary_vector in embedded:
        try:
            if doc.kind == "pdf":
                obsidian.write_generated_note(doc, doc.related, config)
                written += 1
            elif config.rewrite_source_notes:
                if doc.note_path and obsidian.update_related_in_file(
                    doc.note_path, doc.related
                ):
                    written += 1
        except Exception as exc:  # one bad note shouldn't abort the rest
            _log(f"      ! note write failed for '{doc.metadata.title}': {exc}")
            continue

        try:
            store.upsert_document(doc, chunk_vectors, summary_vector)
            if doc.kind == "pdf":
                _cleanup_orphan(old_note_paths.get(doc.doc_id, ""), doc.note_path)
            stored.append(doc)
            h = hash_by_id.get(doc.doc_id)
            if h:
                _record_content_hash(ledger, h, doc.doc_id)
            if doc.kind == "pdf":
                try:
                    touched = knowledge.write_concept_notes(doc, config)
                    if touched:
                        concept_paths.extend(touched)
                        _log(f"      · {len(touched)} concept note(s) → Knowledge Library")
                except Exception as exc:
                    _log(
                        f"      · concept note write failed for "
                        f"'{doc.metadata.title}' ({exc})"
                    )
        except Exception as exc:
            _log(f"      ! store update failed for '{doc.metadata.title}': {exc}")

    # Commit the content-hash ledger only for documents that reached the store.
    _save_hash_ledger(config, ledger)
    docs = stored
    if not docs:
        _log("No document could be stored.")
        return {"processed": 0, "succeeded": []}

    _refresh_related_links(docs, store, config)

    # ── ⑦b cross-link concept notes (semantic, library-wide) ────────
    if config.create_concept_notes and concept_paths:
        _log("  cross-linking concept notes …")
        try:
            n_linked = knowledge.process_concepts(concept_paths, client, store, config)
            if n_linked:
                _log(f"      · linked {n_linked} concept note(s)")
            knowledge.link_siblings(config)
            organize.write_mocs(config)
        except Exception as exc:
            _log(f"      · concept cross-linking failed ({exc})")

    store.optimize()  # keep fragment/version churn in check
    n_docs, n_chunks = store.counts()
    _log(
        f"Done. {len(docs)} processed, {written} note(s) written. "
        f"Store now holds {n_docs} doc(s) / {n_chunks} chunk(s)."
    )
    return {
        "processed": len(docs),
        "written": written,
        "succeeded": [d.doc_id for d in docs],
        "skipped_duplicates": dup_ids,
    }


def _refresh_related_links(docs: list[Document], store: KBStore, config: Config) -> None:
    """Refresh related-paper blocks after successful docs are committed.

    The first related search runs before the current batch is stored, so PDF
    notes can be written before the store/content-hash ledger is finalized. A
    second best-effort pass restores same-batch related links without letting a
    related-block rewrite failure invalidate the now-existing note and store row.
    """
    _log("  refreshing related links …")
    for doc in docs:
        if doc.summary_vector is None:
            continue
        try:
            related = store.related_for_vector(
                doc.summary_vector,
                exclude_doc_id=doc.doc_id,
                k=config.related_top_k,
            )
            targets = [r["link_target"] for r in related if r.get("link_target")]
        except Exception as exc:
            _log(f"      · related refresh failed for '{doc.metadata.title}' ({exc})")
            continue
        if targets == doc.related:
            continue
        doc.related = targets
        try:
            if doc.kind == "pdf":
                obsidian.write_generated_note(doc, doc.related, config)
            elif config.rewrite_source_notes and doc.note_path:
                obsidian.update_related_in_file(doc.note_path, doc.related)
        except Exception as exc:
            _log(f"      · related block rewrite failed for '{doc.metadata.title}' ({exc})")


def _fallback_paper_classification(
    metadata: PaperMetadata, analysis: PaperAnalysis, known_subjects: list[str]
) -> PaperClassification:
    """Best-effort paper filing when the LLM classification call fails.

    Keep the same priority as the normal classifier: metadata-derived
    subdomain/domain first, then analysis/body cues only as a fallback.
    """
    metadata_text = classification_metadata_text(metadata)
    metadata_domain, metadata_subdomain = metadata_classification(
        metadata, known_subjects
    )
    primary = taxonomy.normalize_domain(metadata_domain, known_subjects)
    if not primary:
        primary = taxonomy.classify_text_heuristic(metadata_text, known_subjects)

    fallback_text = "\n".join(
        piece
        for piece in (
            metadata_text,
            analysis.tl_dr,
            analysis.problem_motivation,
            analysis.approach,
            analysis.key_results,
        )
        if piece
    )
    if not primary:
        primary = taxonomy.classify_text_heuristic(fallback_text, known_subjects)

    subdomain = ""
    if primary and metadata_subdomain and metadata_domain.lower() == primary.lower():
        subdomain = metadata_subdomain
    if not subdomain and primary:
        subdomain = taxonomy.classify_subdomain_heuristic(metadata_text, primary)
    if not subdomain and primary:
        subdomain = taxonomy.classify_subdomain_heuristic(fallback_text, primary)

    return PaperClassification(primary_domain=primary, subdomain=subdomain)


def _dedupe_by_content(
    inputs: list[Path], ledger: dict[str, str], known_ids: set[str]
) -> tuple[list[Path], dict[str, str], list[str]]:
    """Drop inputs whose file content is already ingested under another path.

    Returns (kept_inputs, {doc_id: content_hash}, skipped_doc_ids) — the hash
    map is written to the ledger only after the document is actually stored.
    """
    kept: list[Path] = []
    hash_by_id: dict[str, str] = {}
    skipped: list[str] = []
    batch_hashes: set[str] = set()
    for p in inputs:
        h = content_hash_for(p)
        if h is None:
            kept.append(p)
            continue
        if h in batch_hashes:
            _log(f"  · skipping duplicate content (same batch): {p.name}")
            skipped.append(doc_id_for(p))
            continue
        prior = ledger.get(h)
        if prior and prior in known_ids and prior != doc_id_for(p):
            _log(f"  · skipping duplicate content (already ingested): {p.name}")
            skipped.append(doc_id_for(p))
            continue
        batch_hashes.add(h)
        hash_by_id[doc_id_for(p)] = h
        kept.append(p)
    return kept, hash_by_id, skipped


def relink(config: Config) -> dict:
    """Recompute related-literature links for every document in the store."""
    store = KBStore(config)
    all_docs = store.all_docs()
    if not all_docs:
        _log("Store is empty — nothing to relink.")
        return {"updated": 0}

    _log(f"Relinking {len(all_docs)} document(s) …")
    updated = 0
    for row in all_docs:
        related = store.related_for_vector(
            list(row["vector"]), exclude_doc_id=row["doc_id"], k=config.related_top_k
        )
        targets = [r["link_target"] for r in related if r.get("link_target")]
        note_path = row.get("note_path")
        if not note_path:
            continue
        if obsidian.update_related_in_file(Path(note_path), targets):
            updated += 1
    _log(f"Updated related-paper links in {updated} note(s).")

    concept_linked = 0
    if config.create_concept_notes:
        _log("Cross-linking concept notes …")
        client = OllamaClient(config)
        client.unload_llm()  # process_concepts embeds; keep the swap symmetric
        concept_linked = knowledge.process_concepts(None, client, store, config)
        siblings = knowledge.link_siblings(config)
        mocs = organize.write_mocs(config)
        _log(
            f"Linked {concept_linked} concept note(s); siblings on {siblings}; "
            f"{mocs} MOC(s) refreshed."
        )
    return {"updated": updated, "concepts_linked": concept_linked}


def refile_references(
    config: Config, apply: bool = False, plan_out: Path | None = None
) -> dict:
    """File generated paper notes into ``<references>/<Domain>/<Subdomain>/``.

    The subject is derived without the LLM, in this order:
    explicit frontmatter ``Subdomain`` -> metadata fields such as tags, venue,
    DOI/source, and title -> explicit/frontmatter ``Domain`` -> compact body
    sections -> concept majority vote.
    Wikilinks resolve by basename, so moving notes is link-safe; the store's
    ``note_path`` rows are updated to follow.
    """
    refs = config.references_path
    if not refs.exists():
        _log("References folder does not exist yet.")
        return {"moved": 0}

    # concept stem (lower) -> top-level Knowledge Library domain
    kl = config.knowledge_library_path
    domain_of: dict[str, str] = {}
    if kl.exists():
        for p in kl.rglob("*.md"):
            if not p.is_file():
                continue
            rel = p.relative_to(kl).parts
            if len(rel) > 1 and not rel[0].startswith("."):
                domain_of[p.stem.lower()] = rel[0]
    candidates = sorted(set(domain_of.values()) | set(taxonomy.domain_names()))

    # A dry-run is a pure filesystem plan. It must not create a vector store
    # merely to collect note-path bookkeeping used only by --apply.
    store: KBStore | None = None
    path_to_id: dict[str, str] = {}
    if apply:
        store = KBStore(config)
        path_to_id = {
            (r.get("note_path") or ""): r["doc_id"]
            for r in store.all_docs(columns=["doc_id", "note_path"])
        }

    moves: list[tuple[Path, Path, str, str]] = []
    plan_rows: list[dict[str, str]] = []
    for note in sorted(refs.rglob("*.md")):
        if not obsidian.is_generated_note(note):
            continue
        filing = _paper_filing_for_note(note, domain_of, candidates)
        subject, subdomain = filing["domain"], filing["subdomain"]
        if not subject:
            _log(f"  - no subject found (kept in place): {note.stem}")
            plan_rows.append(
                _refile_plan_row("kept-no-domain", note, None, "", "", filing["source"], refs)
            )
            continue
        dest_dir = obsidian.reference_classification_folder(config, subject, subdomain)
        if note.parent.resolve() == dest_dir.resolve():
            plan_rows.append(
                _refile_plan_row("already-filed", note, note, subject, subdomain, filing["source"], refs)
            )
            continue
        dest = dest_dir / note.name
        if dest.exists():
            _log(f"  ! not moved (name already exists at target): {note.name}")
            plan_rows.append(
                _refile_plan_row("blocked-conflict", note, dest, subject, subdomain, filing["source"], refs)
            )
            continue
        moves.append((note, dest, subject, subdomain))
        plan_rows.append(
            _refile_plan_row("move", note, dest, subject, subdomain, filing["source"], refs)
        )
        _log(f"  {note.stem}  ->  {dest_dir.relative_to(refs)}/")

    if not moves:
        _log("Nothing to refile.")
        if plan_out:
            _write_refile_plan(plan_out, plan_rows, refs, apply, moved=0)
        return {"moved": 0}
    if not apply:
        if plan_out:
            _write_refile_plan(plan_out, plan_rows, refs, apply, moved=0)
        _log(f"\nDry run -- {len(moves)} move(s) planned. Re-run with --apply.")
        return {"moved": 0, "planned": len(moves)}

    moved = 0
    for src, dest, subject, subdomain in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        old_str = str(src)
        src.rename(dest)
        _ensure_paper_classification_frontmatter(dest, subject, subdomain)
        moved += 1
        doc_id = path_to_id.get(old_str)
        if doc_id and store is not None:
            try:
                store.update_note_path(doc_id, str(dest))
            except Exception as exc:
                _log(f"  ! store update failed for {dest.name}: {exc}")
    # Drop now-empty leftover dirs (none expected on first run, but tidy).
    for d in sorted((p for p in refs.rglob("*") if p.is_dir()), reverse=True):
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
    if plan_out:
        _write_refile_plan(plan_out, plan_rows, refs, apply, moved=moved)
    _log(f"Moved {moved} note(s) into domain/subdomain folders.")
    return {"moved": moved, "planned": len(moves)}


def _paper_domain_for_note(
    note: Path, domain_of: dict[str, str], candidates: list[str]
) -> tuple[str, str]:
    filing = _paper_filing_for_note(note, domain_of, candidates)
    return filing["domain"], filing["subdomain"]


def _paper_filing_for_note(
    note: Path, domain_of: dict[str, str], candidates: list[str]
) -> dict[str, str]:
    """Domain for an existing paper note, preferring explicit subdomain then metadata."""
    fm = obsidian._read_frontmatter(note)
    metadata_text = _note_metadata_text(note, fm)
    explicit_subdomain = _frontmatter_subdomain(fm, "")
    metadata_domain, metadata_subdomain = taxonomy.classify_subdomain_any(metadata_text)
    if explicit_subdomain:
        domain = taxonomy.domain_for_subdomain(explicit_subdomain)
        if domain:
            return {
                "domain": taxonomy.normalize_domain(domain, candidates),
                "subdomain": explicit_subdomain,
                "source": "frontmatter-subdomain",
            }
    if metadata_domain and metadata_subdomain:
        return {
            "domain": taxonomy.normalize_domain(metadata_domain, candidates),
            "subdomain": metadata_subdomain,
            "source": "metadata",
        }
    for key in ("Domain", "primary_domain", "Primary Domain"):
        value = _frontmatter_get(fm, key)
        if isinstance(value, str) and value.strip():
            domain = taxonomy.normalize_domain(value, candidates)
            subdomain = _frontmatter_subdomain(fm, domain)
            if not subdomain:
                subdomain = taxonomy.classify_subdomain_heuristic(metadata_text, domain)
            if not subdomain:
                subdomain = taxonomy.classify_subdomain_heuristic(
                    _note_body_classification_text(note), domain
                )
                source = "body" if subdomain else "frontmatter-domain"
            else:
                source = (
                    "frontmatter-subdomain"
                    if _frontmatter_subdomain(fm, domain)
                    else "metadata"
                )
            return {"domain": domain, "subdomain": subdomain, "source": source}
    text = obsidian._read_text_tolerant(note)
    guessed = taxonomy.classify_text_heuristic(text[:12000], candidates)
    if guessed:
        subdomain = taxonomy.classify_subdomain_heuristic(metadata_text, guessed)
        source = "metadata" if subdomain else "body-domain"
        if not subdomain:
            subdomain = taxonomy.classify_subdomain_heuristic(
                _note_body_classification_text(note, text), guessed
            )
            source = "body" if subdomain else source
        return {"domain": guessed, "subdomain": subdomain, "source": source}
    voted = _subject_vote(note, domain_of)
    subdomain = (
        taxonomy.classify_subdomain_heuristic(metadata_text, voted)
        or taxonomy.classify_subdomain_heuristic(_note_body_classification_text(note, text), voted)
        if voted
        else ""
    )
    source = "concept-vote"
    if voted and subdomain:
        source = "metadata" if taxonomy.classify_subdomain_heuristic(metadata_text, voted) else "body"
    return {"domain": voted, "subdomain": subdomain, "source": source}


def _refile_plan_row(
    status: str,
    src: Path,
    dest: Path | None,
    domain: str,
    subdomain: str,
    source: str,
    refs: Path,
) -> dict[str, str]:
    return {
        "status": status,
        "source": _rel_for_plan(src, refs),
        "target": _rel_for_plan(dest, refs) if dest else "",
        "domain": domain,
        "subdomain": subdomain,
        "evidence": source,
    }


def _rel_for_plan(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_refile_plan(
    path: Path,
    rows: list[dict[str, str]],
    refs: Path,
    apply: bool,
    moved: int,
) -> Path:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    move_count = sum(1 for r in rows if r["status"] == "move")
    blocked_count = sum(1 for r in rows if r["status"].startswith("blocked"))
    lines = [
        "# PaperRoach Refile Plan",
        "",
        f"- References root: `{refs}`",
        f"- Mode: `{'apply' if apply else 'dry-run'}`",
        f"- Planned moves: {move_count}",
        f"- Applied moves: {moved}",
        f"- Blocked: {blocked_count}",
        "",
        "| Status | Source | Target | Domain | Subdomain | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _md_cell(row[key])
                for key in ("status", "source", "target", "domain", "subdomain", "evidence")
            )
            + " |"
        )
    obsidian.write_text_atomic(path, "\n".join(lines).rstrip() + "\n")
    _log(f"Refile review plan written -> {path}")
    return path


def _md_cell(value: str) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").strip()


def _frontmatter_subdomain(fm: dict, domain: str = "") -> str:
    for key in ("Subdomain", "subdomain", "Primary Subdomain"):
        value = _frontmatter_get(fm, key)
        if isinstance(value, str) and value.strip():
            return taxonomy.normalize_subdomain(value, domain)
    return ""


def _note_metadata_text(note: Path, fm: dict) -> str:
    """Metadata-only signal for filing. This has priority over body text."""
    pieces = [
        note.stem,
        _frontmatter_text(fm, "Domain", "primary_domain", "Primary Domain"),
        _frontmatter_text(fm, "Subdomain", "Primary Subdomain"),
        _frontmatter_text(fm, "tags", "Tags"),
        _frontmatter_text(fm, "Venue", "venue"),
        _frontmatter_text(fm, "Venue Type", "venue_type", "itemType"),
        _frontmatter_text(fm, "DOI", "doi"),
        _frontmatter_text(fm, "Source", "source_url", "url", "URL"),
        _frontmatter_text(fm, "Volume", "volume"),
        _frontmatter_text(fm, "Issue", "issue"),
        _frontmatter_text(fm, "Pages", "pages"),
        _frontmatter_text(fm, "Publisher", "publisher"),
    ]
    return "\n\n".join(p for p in pieces if p)


def _frontmatter_text(fm: dict, *keys: str) -> str:
    return " ".join(_frontmatter_values(_frontmatter_get(fm, *keys)))


def _frontmatter_get(fm: dict, *keys: str):
    """Return a frontmatter value, matching common casing/spacing variants."""
    if not isinstance(fm, dict):
        return None
    lookup = {_frontmatter_key(k): v for k, v in fm.items()}
    for key in keys:
        norm = _frontmatter_key(key)
        if norm in lookup:
            return lookup[norm]
    return None


def _frontmatter_key(key: object) -> str:
    return re.sub(r"[\s_\-]+", "", str(key or "").strip().lower())


def _frontmatter_values(value) -> list[str]:
    """Normalize scalar or sequence frontmatter values into text values."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, (list, tuple, set)):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]


def _note_body_classification_text(note: Path, text: str | None = None) -> str:
    """Compact body signal for existing generated notes.

    Full generated notes contain broad words like "algorithm" and "training"
    that can overpower the actual filing topic. Use it only after metadata.
    """
    text = text if text is not None else obsidian._read_text_tolerant(note)
    pieces = []
    for heading in (
        "TL;DR",
        "Problem & Motivation",
        "Approach",
        "Key Results",
        "Concepts",
    ):
        m = re.search(rf"(?ms)^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text)
        if m:
            pieces.append(m.group(1).strip()[:2500])
    return "\n\n".join(p for p in pieces if p)


def _ensure_paper_classification_frontmatter(
    note: Path, domain: str, subdomain: str
) -> bool:
    """Persist inferred filing fields so future refile runs are stable."""
    fm_text, body = obsidian.split_frontmatter(obsidian._read_text_tolerant(note))
    if fm_text is None:
        return False
    fm = obsidian._read_frontmatter(note)
    if not isinstance(fm, dict):
        return False
    changed = False
    if domain and not str(fm.get("Domain") or "").strip():
        fm["Domain"] = domain
        changed = True
    if subdomain and not str(fm.get("Subdomain") or "").strip():
        fm["Subdomain"] = subdomain
        changed = True
    if not changed:
        return False
    obsidian.write_text_atomic(
        note, f"---\n{obsidian._dump_yaml(fm).rstrip()}\n---\n{body}"
    )
    return True


def _subject_vote(note: Path, domain_of: dict[str, str]) -> str:
    """Majority Knowledge Library domain among the note's ## Concepts links."""
    text = obsidian._read_text_tolerant(note)
    m = re.search(r"(?ms)^## Concepts\s*$(.*?)(?=^## |\Z)", text)
    if not m:
        return ""
    votes: dict[str, int] = {}
    for target in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", m.group(1)):
        domain = domain_of.get(target.strip().lower())
        if domain:
            votes[domain] = votes.get(domain, 0) + 1
    if not votes:
        return ""
    return max(sorted(votes), key=lambda d: votes[d])


_RETAG_SYSTEM = (
    "You are curating the tag taxonomy of a research-paper library. You get "
    "the library's current tags with usage counts. Consolidate them into a "
    "clean, controlled vocabulary:\n"
    "- Merge spelling variants, synonyms and near-duplicates into ONE "
    "canonical tag (lowercase, hyphen-separated English), e.g. "
    "computervision/computer-vision -> computer-vision.\n"
    "- Drop tags that are noise for a paper library (stray publisher "
    "keywords such as 'costs' or 'power-generation', one-off overly "
    "specific tags that will never be reused).\n"
    "- Keep the vocabulary compact: broad, reusable topic tags.\n"
    "- When a variant matches one of the EXISTING canonical tags listed by "
    "the user, map it onto that existing tag instead of inventing another.\n"
    'Return ONLY JSON: {"tags": [{"tag": "<canonical>", "description": '
    '"<one short line, in English>", "aliases": ["<merged variant>", ...]}], '
    '"drop": ["<tag to remove entirely>", ...]}. '
    "Every input tag must appear exactly once — as a canonical tag, inside "
    "an aliases list, or in drop. Keep descriptions short. No <think> block."
)


def retag(config: Config, apply: bool = False) -> dict:
    """Consolidate the tags of every generated paper note into a controlled
    vocabulary, and document it in the vault's Tag Registry.

    Only kb-generated notes under the references folder are touched — user
    notes, concept notes and MOCs keep their own tags.
    """
    refs = config.references_path
    notes = [p for p in refs.rglob("*.md") if obsidian.is_generated_note(p)]
    if not notes:
        _log("No generated paper notes found.")
        return {"updated": 0}

    # Current tag usage ('paper' is structural — always kept, never curated).
    note_tags: dict[Path, list[str]] = {}
    counts: dict[str, int] = {}
    for p in notes:
        fm = obsidian._read_frontmatter(p)
        raw = fm.get("tags") or []
        if isinstance(raw, str):
            raw = [raw]
        cur = [str(t) for t in raw if str(t).strip().lower() != "paper"]
        note_tags[p] = cur
        for t in cur:
            counts[t] = counts.get(t, 0) + 1
    if not counts:
        _log("Paper notes carry no tags to consolidate.")
        return {"updated": 0}

    _log(f"{len(counts)} distinct tag(s) across {len(notes)} paper note(s).")
    client = OllamaClient(config)
    client.ping()
    client.unload_embed()

    # Consolidate in batches: one giant call would need a JSON answer near
    # the model's context limit (slow, and it can truncate mid-object).
    # Earlier batches' canonical tags are offered to later batches, so
    # variants converge instead of re-inventing near-duplicates.
    registry = tags_mod.load_registry(config)
    dropped: set[str] = set()
    ordered = [t for t, _n in sorted(counts.items(), key=lambda kv: -kv[1])]
    batches = list(knowledge._batches(ordered, 40))
    for bi, batch in enumerate(batches, 1):
        _log(f"  consolidating batch {bi}/{len(batches)} ({len(batch)} tag(s)) …")
        listing = "\n".join(f"- {t}  (used {counts[t]}x)" for t in batch)
        known = ", ".join(registry) if registry else "(none yet)"
        obj = client.generate_json(
            _RETAG_SYSTEM,
            f"Existing canonical tags (prefer these):\n{known}\n\n"
            f"Current tags:\n{listing}\n\nReturn the JSON now.",
        )
        dropped |= {tags_mod.normalize(t) for t in (obj.get("drop") or [])}
        # Merge into the registry (user-edited descriptions win; new
        # aliases are appended).
        for item in obj.get("tags") or []:
            if not isinstance(item, dict) or not item.get("tag"):
                continue
            tag = tags_mod.normalize(item["tag"])
            if not tag:
                continue
            entry = registry.setdefault(tag, {"description": "", "aliases": []})
            if not entry["description"]:
                entry["description"] = str(item.get("description") or "").strip()
            for alias in item.get("aliases") or []:
                alias = tags_mod.normalize(alias)
                if alias and alias != tag and alias not in entry["aliases"]:
                    entry["aliases"].append(alias)

    # Plan the per-note rewrite.
    changes: list[tuple[Path, list[str]]] = []
    for p, cur in note_tags.items():
        kept = [t for t in cur if tags_mod.normalize(t) not in dropped]
        new = tags_mod.canonicalize(kept, registry)
        if new != cur:
            changes.append((p, new))

    _log(f"Vocabulary: {len(registry)} canonical tag(s); dropping {len(dropped)}.")
    _log(f"{len(changes)} of {len(notes)} note(s) would change, e.g.:")
    for p, new in changes[:8]:
        _log(f"  {p.stem[:60]}")
        _log(f"      {note_tags[p]}  →  {new}")

    if not apply:
        _log("\nDry run — nothing written. Re-run `paperroach retag --apply` to commit.")
        return {"updated": 0}

    reg_path = tags_mod.save_registry(config, registry)
    _log(f"Tag Registry written → {reg_path}")
    updated = 0
    for p, new in changes:
        if knowledge._ensure_list_props(
            p, [("tags", ["paper"] + new, "Source")], overwrite=True
        ):
            updated += 1
    _log(f"Rewrote tags in {updated} note(s).")
    return {"updated": updated}


_RETAG_CONCEPTS_SYSTEM = (
    "You are enriching the tags of notes in a personal knowledge library. "
    "For EACH note you get its name, folder and a body excerpt. Propose 3-5 "
    "topical tags per note (technique, task, model family, math area …) — "
    "lowercase, hyphen-separated English; specific enough to group related "
    "notes across folders, general enough to be reused. PREFER the existing "
    "canonical tags listed by the user when they fit; do not repeat the "
    "folder name itself. "
    'Return ONLY JSON: {"notes": [{"name": "<exact name as given>", '
    '"tags": ["…", …]}]}. Every input note must appear exactly once. '
    "No <think> block."
)


def retag_concepts(config: Config, apply: bool = False) -> dict:
    """Enrich every kb-generated concept note with 3-5 topical tags (LLM).

    Concept notes historically carried only their subject as a tag; this pass
    draws tags from (and appends new ones to) the same Tag Registry vocabulary
    the paper notes use. Existing tags on a note are kept, new ones appended.
    """
    kl = config.knowledge_library_path
    notes = [
        p
        for p in sorted(kl.rglob("*.md"))
        if p.is_file()
        and obsidian.is_generated_note(p)
        and not p.stem.endswith(" MOC")
    ]
    if not notes:
        _log("No generated concept notes found.")
        return {"updated": 0}
    _log(f"Tagging {len(notes)} concept note(s) …")

    client = OllamaClient(config)
    client.ping()
    client.unload_embed()

    registry = tags_mod.load_registry(config)
    proposals: dict[Path, list[str]] = {}
    batches = list(knowledge._batches(notes, 10))
    for bi, batch in enumerate(batches, 1):
        _log(f"  batch {bi}/{len(batches)} ({len(batch)} note(s)) …")
        by_key = {normalize_concept_key(p.stem): p for p in batch}
        known = ", ".join(registry) if registry else "(none yet)"
        listing = "\n\n".join(
            f"### {p.stem}\nFolder: {p.parent.relative_to(kl).as_posix() or '(root)'}\n"
            + knowledge._note_body(p)[:300]
            for p in batch
        )
        try:
            obj = client.generate_json(
                _RETAG_CONCEPTS_SYSTEM,
                f"Existing canonical tags (prefer these):\n{known}\n\n"
                f"{listing}\n\nReturn the JSON now.",
            )
        except Exception as exc:
            _log(f"      ! batch failed ({exc}); skipping")
            continue
        index = tags_mod.alias_index(registry)
        for item in obj.get("notes") or []:
            if not isinstance(item, dict):
                continue
            p = by_key.get(normalize_concept_key(str(item.get("name") or "")))
            if p is None:
                continue  # hallucinated / mangled note name
            raw = item.get("tags")
            if isinstance(raw, str):
                raw = [raw]
            new = tags_mod.canonicalize(raw or [], registry, limit=5)
            if not new:
                continue
            proposals[p] = new
            # Grow the vocabulary as we go so later batches converge on it.
            for t in new:
                if tags_mod._squash(t) not in index:
                    registry[t] = {"description": "", "aliases": []}
                    index[tags_mod._squash(t)] = t

    # Merge: keep the note's current tags (subject tag first), append new.
    changes: list[tuple[Path, list[str], list[str]]] = []
    for p, new in proposals.items():
        raw = obsidian._read_frontmatter(p).get("tags") or []
        if isinstance(raw, str):
            raw = [raw]
        cur = [str(t) for t in raw if str(t).strip()]
        seen = {tags_mod._squash(t) for t in cur}
        merged = cur + [t for t in new if tags_mod._squash(t) not in seen]
        merged = merged[: tags_mod.MAX_TAGS_PER_NOTE]
        if merged != cur:
            changes.append((p, cur, merged))

    _log(f"{len(changes)} of {len(notes)} note(s) would change, e.g.:")
    for p, cur, merged in changes[:8]:
        _log(f"  {p.stem[:60]}")
        _log(f"      {cur}  →  {merged}")
    if not apply:
        _log(
            "\nDry run — nothing written. "
            "Re-run `paperroach retag --concepts --apply` to commit."
        )
        return {"updated": 0}

    reg_path = tags_mod.save_registry(config, registry)
    _log(f"Tag Registry written → {reg_path}")
    updated = 0
    for p, _cur, merged in changes:
        if knowledge._ensure_list_props(
            p, [("tags", merged, "Status")], overwrite=True
        ):
            updated += 1
    _log(f"Rewrote tags in {updated} note(s).")
    return {"updated": updated}


def _generated_source_hash(row: dict) -> str | None:
    """Return a duplicate-proof hash for a generated PDF note, if available."""
    if row.get("kind") != "pdf":
        return None
    note_value = str(row.get("note_path") or "").strip()
    if not note_value:
        return None
    note = Path(note_value)
    if not note.exists() or not obsidian.is_generated_note(note):
        return None
    source = obsidian._read_frontmatter(note).get("kb-source")
    if not isinstance(source, str) or not source.strip():
        return None
    return content_hash_for(Path(source).expanduser())


def _duplicate_rows(docs: list[dict], orphan_ids: set[str]) -> tuple[list[dict], list[dict]]:
    """Return confirmed duplicates plus possible title/year matches.

    A matching title/year only identifies candidates. Automatic removal requires
    generated PDF notes whose source files still have identical bytes.
    """
    by_title_year: dict[tuple[str, object], list[dict]] = {}
    for row in docs:
        if row["doc_id"] in orphan_ids:
            continue
        title = str(row.get("title") or "").strip().lower()
        if title:
            by_title_year.setdefault((title, row.get("year")), []).append(row)

    confirmed: list[dict] = []
    possible: list[dict] = []
    for rows in by_title_year.values():
        if len(rows) < 2:
            continue
        by_hash: dict[str, list[dict]] = {}
        for row in rows:
            source_hash = _generated_source_hash(row)
            if source_hash:
                by_hash.setdefault(source_hash, []).append(row)

        proven_ids: set[str] = set()
        for same_content in by_hash.values():
            if len(same_content) < 2:
                continue
            ordered = sorted(
                same_content,
                key=lambda row: (len(str(row.get("note_path") or "")), row["doc_id"]),
            )
            proven_ids.update(row["doc_id"] for row in ordered)
            confirmed.extend(ordered[1:])
        possible.extend(row for row in rows if row["doc_id"] not in proven_ids)
    return confirmed, possible


def gc(config: Config, apply: bool = False) -> dict:
    """Report (and with ``apply`` remove) stale rows and proven duplicates.

    * doc/concept rows whose note file no longer exists (deleted or renamed
      outside the pipeline) — these otherwise haunt related-links forever.
    * generated PDF notes whose source bytes match exactly. Title/year matches
      without that proof remain visible for manual review and are never deleted.
    """
    if not table_names(config):
        _log("Store is not initialized -- nothing to clean.")
        return {"removed": 0}

    store = KBStore(config)
    docs = store.all_docs(
        columns=["doc_id", "title", "year", "kind", "note_path", "link_target"]
    )

    orphans = [
        r for r in docs
        if (r.get("note_path") or "") and not Path(r["note_path"]).exists()
    ]
    orphan_ids = {r["doc_id"] for r in orphans}

    dups, possible_dups = _duplicate_rows(docs, orphan_ids)

    concept_orphans = [
        r for r in store.all_concepts()
        if (r.get("note_path") or "") and not Path(r["note_path"]).exists()
    ]

    _log(f"Orphaned document rows : {len(orphans)}")
    for r in orphans:
        _log(f"  - {r.get('title') or r['doc_id']}  (note missing: {r.get('note_path')})")
    _log(f"Confirmed duplicates  : {len(dups)}")
    for r in dups:
        _log(f"  - {r.get('title')}  ({r.get('note_path')})")
    _log(f"Possible title matches: {len(possible_dups)}")
    for r in possible_dups:
        _log(f"  - {r.get('title')}  ({r.get('note_path')})")
    _log(f"Orphaned concept rows  : {len(concept_orphans)}")
    for r in concept_orphans:
        _log(f"  - {r.get('name')}  (note missing: {r.get('note_path')})")

    cleanup_candidates = orphans or dups or concept_orphans
    if not cleanup_candidates:
        if possible_dups:
            _log("No confirmed cleanup candidates. Review possible title matches manually.")
        else:
            _log("Store is clean.")
        return {"removed": 0, "possible_duplicates": len(possible_dups)}
    if not apply:
        _log("\nDry run — nothing deleted. Re-run `paperroach gc --apply` to clean up.")
        return {"removed": 0, "possible_duplicates": len(possible_dups)}

    removed = 0
    for r in orphans:
        store.delete_doc(r["doc_id"])
        removed += 1
    for r in dups:
        note_path = Path(r["note_path"]) if r.get("note_path") else None
        if note_path and note_path.exists() and obsidian.is_generated_note(note_path):
            try:
                note_path.unlink()
                _log(f"  · removed duplicate note: {note_path.name}")
            except OSError:
                _log(f"  ! could not remove duplicate note: {note_path}")
                continue
        store.delete_doc(r["doc_id"])
        removed += 1
    for r in concept_orphans:
        store.delete_concept(r["concept_id"])
        removed += 1
    store.optimize()
    _log(f"Removed {removed} stale/duplicate entr(ies).")
    return {"removed": removed, "possible_duplicates": len(possible_dups)}


def watch(config: Config, scan_only: bool = False) -> dict:
    """Auto-detect new Zotero PDFs and build them.

    ``scan_only`` processes everything not yet in the store once and exits;
    otherwise this polls ``storage/`` every ``watch_interval`` seconds until
    interrupted. Already-ingested PDFs are skipped via their stable doc_id.
    """
    data_dir = zotero.find_data_dir(config)
    if data_dir is None:
        _log(
            "Could not locate the Zotero data directory. Set zotero_dir in "
            "kb.toml or pass --zotero-dir."
        )
        return {"processed": 0}
    config.ensure_dirs()

    # Shared writer guard: watchers and manual maintenance commands all touch
    # the same notes/store, so they coordinate through one lock file.
    fresh_window = max(60.0, config.watch_interval * 5.0)
    try:
        # The watcher only holds the writer lock while it initializes or builds.
        # Keeping it for the full daemon lifetime blocks unrelated manual work.
        with nullcontext():
            _MAX_ATTEMPTS = 3
            # Refresh stored ids only after acquiring the short-lived build lock.
            # This lets a long-running watcher coexist with manual writers.
            seen: set[str] = set()
            attempts: dict[str, int] = {}  # doc_id -> failed build attempts
            storage = data_dir / "storage"
            _log(f"Zotero data dir : {data_dir}")
            _log(f"Watching        : {storage}")
            if not scan_only:
                _log(f"Polling every {config.watch_interval}s. Press Ctrl+C to stop.")

            total = 0
            while True:
                new = []
                for pdf in zotero.storage_pdfs(data_dir):
                    did = doc_id_for(pdf)
                    if did in seen:
                        continue
                    if attempts.get(did, 0) >= _MAX_ATTEMPTS:
                        continue  # kept failing; don't burn the LLM on it every cycle
                    if not _stable(pdf):
                        continue  # still downloading; pick it up next cycle
                    new.append(pdf)
                if new:
                    _log(f"\nDetected {len(new)} new PDF(s) in Zotero:")
                    for p in new:
                        _log(f"  + {p.name}")
                    locked = False
                    try:
                        with PipelineLock(
                            config, "watch-build", stale_seconds=fresh_window
                        ):
                            current_seen = {
                                row["doc_id"]
                                for row in KBStore(config).all_docs(columns=["doc_id"])
                            }
                            seen |= current_seen
                            batch = [p for p in new if doc_id_for(p) not in seen]
                            result = build(batch, config) if batch else {"succeeded": []}
                    except PipelineLockError as exc:
                        _log(f"  ! writer is busy ({exc}); will retry")
                        result = {"succeeded": []}
                        locked = True
                    except Exception as exc:
                        # The watcher daemon must survive anything a build throws.
                        _log(f"  ! build failed: {exc}")
                        result = {"succeeded": []}
                    # Only successfully stored documents are done; a failed PDF gets
                    # retried (up to _MAX_ATTEMPTS) instead of being skipped forever.
                    # Content-duplicates count as done too.
                    succeeded = set(result.get("succeeded") or [])
                    seen |= succeeded | set(result.get("skipped_duplicates") or [])
                    if not locked:
                        for p in new:
                            did = doc_id_for(p)
                            if did not in seen:
                                attempts[did] = attempts.get(did, 0) + 1
                                if attempts[did] == _MAX_ATTEMPTS:
                                    _log(
                                        f"  ! giving up on {p.name} after "
                                        f"{_MAX_ATTEMPTS} attempts"
                                    )
                    total += len(succeeded)
                    if locked and scan_only:
                        return {"processed": total, "locked": True}
                if scan_only:
                    _log(f"Scan complete. {total} new document(s) processed.")
                    return {"processed": total}
                time.sleep(config.watch_interval)
    except PipelineLockError as exc:
        _log(str(exc))
        return {"processed": 0, "locked": True}


def integrate_note_equations(path: Path, client: OllamaClient, config: Config) -> bool:
    """Rewrite an existing paper note so the equations in its ``## Key Equations``
    section are woven into the ``## Approach`` prose, then remove the separate
    section. No re-ingestion needed — operates on the note file."""
    text = obsidian._read_text_tolerant(path)
    ke = re.search(r"(?ms)^## Key Equations\b(.*?)(?=^## |\Z)", text)
    if not ke:
        return False
    eqs = [
        " ".join(e.split()).strip()
        for e in re.findall(r"\$\$(.+?)\$\$", ke.group(1), re.DOTALL)
    ]
    eqs = [e for e in eqs if len(e) >= 4]
    if not eqs:
        return False

    ap = re.search(r"(?ms)^## Approach\b[^\n]*\n(.*?)(?=^## |\Z)", text)
    if ap is None:
        # Nowhere to weave the equations into — leave the Key Equations
        # section untouched rather than deleting the only copy of the math.
        return False
    approach = ap.group(1).strip()
    tm = re.search(r"(?m)^#\s+(.+)$", text)
    title = tm.group(1).strip() if tm else path.stem

    new_approach = write_integrated_approach(client, title, approach, eqs, config)
    if not new_approach.strip():
        return False  # integration produced nothing; keep the original note
    # splice (not re.sub — the LaTeX has backslashes)
    text = text[: ap.start(1)] + new_approach + "\n\n" + text[ap.end(1):]
    # remove the now-redundant Key Equations section (also when it is the
    # last section of the note — hence the \Z alternative)
    text = re.sub(r"(?ms)\n## Key Equations\b.*?(?=\n## |\Z)", "\n", text, count=1)
    obsidian.write_text_atomic(path, obsidian.fix_inline_math(text))
    return True


def fix_math_in_all_notes(config: Config) -> int:
    """Retroactively strip spaces inside inline math (`$ x $` -> `$x$`) in every
    kb-generated note (paper + concept). User-authored notes are left alone."""
    fixed = 0
    seen: set = set()
    for base in (config.references_path, config.knowledge_library_path):
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            if p in seen or not obsidian.is_generated_note(p):
                continue
            seen.add(p)
            original = obsidian._read_text_tolerant(p)
            new = obsidian.fix_inline_math(original)
            if new != original:
                obsidian.write_text_atomic(p, new)
                fixed += 1
    return fixed


def integrate_all_equations(config: Config) -> int:
    """Weave equations into every generated paper note that still has a separate
    ``## Key Equations`` section."""
    client = OllamaClient(config)
    refs = config.references_path
    count = 0
    for path in sorted(refs.rglob("*.md")):
        if not obsidian.is_generated_note(path):
            continue
        _log(f"  {path.stem}")
        try:
            if integrate_note_equations(path, client, config):
                count += 1
        except Exception as exc:
            _log(f"    ! failed: {exc}")
    return count


_EQ_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)


def _extract_equations(markdown: str, limit: int = 20) -> list[str]:
    """Pull verbatim display equations ($$...$$) from the source markdown."""
    out, seen = [], set()
    for m in _EQ_RE.finditer(markdown):
        eq = " ".join(m.group(1).split()).strip()
        if len(eq) < 4 or eq in seen:
            continue
        seen.add(eq)
        out.append(eq)
        if len(out) >= limit:
            break
    return out


def _stable(path: Path, min_age: float = 3.0) -> bool:
    """True if the file hasn't been modified very recently (write finished)."""
    try:
        return (time.time() - path.stat().st_mtime) >= min_age
    except OSError:
        return False
