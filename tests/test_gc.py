import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kb.config import Config
from kb.pipeline import gc
from kb.store import KBStore


def _gc_quietly(*args, **kwargs):
    result, _output = _capture_gc(*args, **kwargs)
    return result


def _capture_gc(*args, **kwargs):
    stdout = StringIO()
    with redirect_stdout(stdout):
        result = gc(*args, **kwargs)
    return result, stdout.getvalue()


def _cfg(root: Path) -> Config:
    return Config(vault_path=root / "vault", kb_dir=".kb", embed_dim=2)


def _doc_row(doc_id: str, title: str, note_path: Path | str, *, year: int = 2024) -> dict:
    return {
        "doc_id": doc_id,
        "title": title,
        "authors": ["Test Author"],
        "year": year,
        "kind": "pdf",
        "note_path": str(note_path),
        "link_target": Path(note_path).stem if note_path else "",
        "summary": "",
        "tags": ["paper"],
        "vector": [1.0, 0.0],
    }


def _chunk_row(doc_id: str, note_path: Path | str) -> dict:
    return {
        "id": f"{doc_id}:0",
        "doc_id": doc_id,
        "note_path": str(note_path),
        "title": "Test Paper",
        "header": "TL;DR",
        "text": "A test chunk.",
        "chunk_index": 0,
        "vector": [1.0, 0.0],
    }


def _concept_row(concept_id: str, note_path: Path | str) -> dict:
    return {
        "concept_id": concept_id,
        "name": "Test Concept",
        "note_path": str(note_path),
        "subject": "Computer Science",
        "vector": [0.0, 1.0],
    }


def _write_generated_note(path: Path, source_path: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    source_line = (
        f'kb-source: "{source_path.as_posix()}"'
        if source_path is not None
        else ""
    )
    path.write_text(
        "\n".join(
            [
                "---",
                "Type:",
                "- Paper",
                "kb-generated: true",
                source_line,
                "---",
                f"# {path.stem}",
                "",
            ]
        ),
        encoding="utf-8",
    )


class GCTests(unittest.TestCase):
    def test_gc_dry_run_does_not_initialize_empty_store(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(Path(td))
            cfg.vault_path.mkdir()

            result, output = _capture_gc(cfg, apply=False)

            self.assertEqual(result["removed"], 0)
            self.assertIn("Store is not initialized", output)
            self.assertFalse(cfg.kb_path.exists())

    def test_gc_dry_run_keeps_orphan_rows(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(Path(td))
            store = KBStore(cfg)
            missing_note = cfg.references_path / "Missing Paper.md"
            missing_concept = cfg.knowledge_library_path / "Missing Concept.md"
            store.docs.add([
                _doc_row("aaaaaaaaaaaa", "Missing Paper", missing_note),
            ])
            store.chunks.add([_chunk_row("aaaaaaaaaaaa", missing_note)])
            store.concepts.add([_concept_row("concept-a", missing_concept)])

            result, output = _capture_gc(cfg, apply=False)

            self.assertEqual(result["removed"], 0)
            self.assertIn("paperroach gc --apply", output)
            self.assertNotIn("kb gc --apply", output)
            self.assertEqual(store.docs.count_rows(), 1)
            self.assertEqual(store.chunks.count_rows(), 1)
            self.assertEqual(store.concepts.count_rows(), 1)

    def test_gc_apply_removes_orphans_and_duplicate_generated_note(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(Path(td))
            store = KBStore(cfg)
            keeper = cfg.references_path / "Test Paper (2024).md"
            duplicate = cfg.references_path / "Test Paper (2024) (2).md"
            missing_note = cfg.references_path / "Missing Paper.md"
            missing_concept = cfg.knowledge_library_path / "Missing Concept.md"
            first_source = Path(td) / "first.pdf"
            second_source = Path(td) / "second.pdf"
            first_source.write_bytes(b"same paper bytes")
            second_source.write_bytes(b"same paper bytes")
            _write_generated_note(keeper, first_source)
            _write_generated_note(duplicate, second_source)

            store.docs.add(
                [
                    _doc_row("aaaaaaaaaaaa", "Missing Paper", missing_note),
                    _doc_row("bbbbbbbbbbbb", "Test Paper", keeper),
                    _doc_row("cccccccccccc", "Test Paper", duplicate),
                ]
            )
            store.chunks.add(
                [
                    _chunk_row("aaaaaaaaaaaa", missing_note),
                    _chunk_row("bbbbbbbbbbbb", keeper),
                    _chunk_row("cccccccccccc", duplicate),
                ]
            )
            store.concepts.add([_concept_row("concept-a", missing_concept)])

            result = _gc_quietly(cfg, apply=True)
            reopened = KBStore(cfg)
            remaining_docs = reopened.all_docs(columns=["doc_id", "note_path"])
            remaining_doc_ids = {row["doc_id"] for row in remaining_docs}
            remaining_chunks = {
                row["doc_id"] for row in reopened.chunks.to_arrow().to_pylist()
            }

            self.assertEqual(result["removed"], 3)
            self.assertEqual(remaining_doc_ids, {"bbbbbbbbbbbb"})
            self.assertEqual(remaining_chunks, {"bbbbbbbbbbbb"})
            self.assertEqual(reopened.concepts.count_rows(), 0)
            self.assertTrue(keeper.exists())
            self.assertFalse(duplicate.exists())

    def test_gc_keeps_same_title_year_when_source_bytes_differ(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(Path(td))
            store = KBStore(cfg)
            first = cfg.references_path / "Shared Title (2024).md"
            second = cfg.references_path / "Shared Title (2024) (2).md"
            first_source = Path(td) / "first.pdf"
            second_source = Path(td) / "second.pdf"
            first_source.write_bytes(b"first paper")
            second_source.write_bytes(b"different paper")
            _write_generated_note(first, first_source)
            _write_generated_note(second, second_source)
            store.docs.add(
                [
                    _doc_row("aaaaaaaaaaaa", "Shared Title", first),
                    _doc_row("bbbbbbbbbbbb", "Shared Title", second),
                ]
            )
            store.chunks.add(
                [
                    _chunk_row("aaaaaaaaaaaa", first),
                    _chunk_row("bbbbbbbbbbbb", second),
                ]
            )

            result, output = _capture_gc(cfg, apply=True)

            self.assertEqual(result["removed"], 0)
            self.assertEqual(result["possible_duplicates"], 2)
            self.assertIn("Possible title matches: 2", output)
            self.assertIn("Review possible title matches manually", output)
            self.assertNotIn("Store is clean.", output)
            self.assertEqual(store.docs.count_rows(), 2)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())


if __name__ == "__main__":
    unittest.main()
