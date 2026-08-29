import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kb.models import content_hash_for, doc_id_for
from kb.pipeline import _dedupe_by_content, _record_content_hash


class ContentDedupeTests(unittest.TestCase):
    def _dedupe_quietly(self, *args, **kwargs):
        with redirect_stdout(StringIO()):
            return _dedupe_by_content(*args, **kwargs)

    def test_content_hash_returns_none_for_missing_file(self):
        self.assertIsNone(content_hash_for(Path("does-not-exist.pdf")))

    def test_dedupe_skips_second_copy_in_same_batch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_bytes(b"same content")
            second.write_bytes(b"same content")

            kept, hash_by_id, skipped = self._dedupe_quietly(
                [first, second],
                ledger={},
                known_ids=set(),
            )

            self.assertEqual(kept, [first])
            self.assertEqual(skipped, [doc_id_for(second)])
            self.assertEqual(set(hash_by_id), {doc_id_for(first)})

    def test_dedupe_skips_content_known_under_another_doc_id(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_path = root / "old.pdf"
            new_path = root / "new.pdf"
            old_path.write_bytes(b"already indexed")
            new_path.write_bytes(b"already indexed")
            old_doc_id = doc_id_for(old_path)
            content_hash = content_hash_for(old_path)
            assert content_hash is not None

            kept, hash_by_id, skipped = self._dedupe_quietly(
                [new_path],
                ledger={content_hash: old_doc_id},
                known_ids={old_doc_id},
            )

            self.assertEqual(kept, [])
            self.assertEqual(hash_by_id, {})
            self.assertEqual(skipped, [doc_id_for(new_path)])

    def test_dedupe_keeps_same_path_even_when_hash_is_already_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "paper.pdf"
            path.write_bytes(b"same path rebuild")
            doc_id = doc_id_for(path)
            content_hash = content_hash_for(path)
            assert content_hash is not None

            kept, hash_by_id, skipped = self._dedupe_quietly(
                [path],
                ledger={content_hash: doc_id},
                known_ids={doc_id},
            )

            self.assertEqual(kept, [path])
            self.assertEqual(hash_by_id, {doc_id: content_hash})
            self.assertEqual(skipped, [])

    def test_record_content_hash_retires_previous_hash_for_same_document(self):
        ledger = {
            "oldhash": "aaaaaaaaaaaa",
            "otherhash": "bbbbbbbbbbbb",
        }

        _record_content_hash(ledger, "newhash", "aaaaaaaaaaaa")

        self.assertEqual(
            ledger,
            {
                "newhash": "aaaaaaaaaaaa",
                "otherhash": "bbbbbbbbbbbb",
            },
        )


if __name__ == "__main__":
    unittest.main()
