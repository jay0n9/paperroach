import tempfile
import unittest
import warnings
import json
from pathlib import Path
from unittest.mock import patch

from kb.config import Config
from kb.store import (
    KBStore,
    STORE_SCHEMA_VERSION,
    _store_meta_path,
    row_counts,
    table_names,
)


class StoreTests(unittest.TestCase):
    def test_table_names_does_not_create_store_metadata_for_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Config(vault_path=Path(td) / "vault", kb_dir=".kb", embed_dim=3)
            cfg.kb_path.mkdir(parents=True)

            self.assertEqual(table_names(cfg), set())
            self.assertFalse(_store_meta_path(cfg).exists())

    def test_store_initialization_writes_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Config(
                vault_path=Path(td) / "vault",
                kb_dir=".kb",
                embed_model="test-embedder",
                embed_dim=3,
            )

            KBStore(cfg)

            meta = json.loads(_store_meta_path(cfg).read_text(encoding="utf-8"))
            self.assertEqual(
                meta,
                {
                    "schema_version": STORE_SCHEMA_VERSION,
                    "embed_model": "test-embedder",
                    "embed_dim": 3,
                },
            )

    def test_store_rejects_same_dimension_different_embedding_model(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            cfg = Config(
                vault_path=root,
                kb_dir=".kb",
                embed_model="first-model",
                embed_dim=3,
            )
            KBStore(cfg)

            changed = Config(
                vault_path=root,
                kb_dir=".kb",
                embed_model="second-model",
                embed_dim=3,
            )
            with self.assertRaises(RuntimeError) as raised:
                KBStore(changed)

            self.assertIn("embed_model='first-model'", str(raised.exception))

    def test_row_counts_rejects_embedding_model_mismatch_without_rewriting(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            cfg = Config(
                vault_path=root,
                kb_dir=".kb",
                embed_model="first-model",
                embed_dim=3,
            )
            KBStore(cfg)
            changed = Config(
                vault_path=root,
                kb_dir=".kb",
                embed_model="second-model",
                embed_dim=3,
            )

            with patch("kb.store.os.replace") as replace:
                with self.assertRaises(RuntimeError) as raised:
                    row_counts(changed)

            self.assertIn("embed_model='first-model'", str(raised.exception))
            replace.assert_not_called()

    def test_store_does_not_rewrite_matching_metadata_on_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Config(vault_path=Path(td) / "vault", kb_dir=".kb", embed_dim=3)
            KBStore(cfg)

            with patch("kb.store.os.replace") as replace:
                KBStore(cfg)

            replace.assert_not_called()

    def test_store_rejects_invalid_metadata_file(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Config(vault_path=Path(td) / "vault", kb_dir=".kb", embed_dim=3)
            cfg.kb_path.mkdir(parents=True)
            _store_meta_path(cfg).write_text("{not json", encoding="utf-8")

            with self.assertRaises(RuntimeError) as raised:
                KBStore(cfg)

            self.assertIn("Invalid store metadata", str(raised.exception))

    def test_store_initialization_avoids_deprecated_table_names_warning(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Config(vault_path=Path(td) / "vault", kb_dir=".kb")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", DeprecationWarning)
                KBStore(cfg)

            messages = [str(w.message) for w in caught]
            self.assertFalse(
                any("table_names()" in message for message in messages),
                messages,
            )


if __name__ == "__main__":
    unittest.main()
