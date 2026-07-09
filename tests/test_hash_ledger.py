import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb.config import Config
from kb.pipeline import _hash_ledger_path, _load_hash_ledger, _save_hash_ledger


class HashLedgerTests(unittest.TestCase):
    def test_save_hash_ledger_replaces_existing_file_atomically(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td) / "vault", kb_dir=".kb")
            config.ensure_dirs()

            _save_hash_ledger(config, {"oldhash": "aaaaaaaaaaaa"})
            _save_hash_ledger(config, {"newhash": "bbbbbbbbbbbb"})

            self.assertEqual(_load_hash_ledger(config), {"newhash": "bbbbbbbbbbbb"})

    def test_failed_hash_ledger_save_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td) / "vault", kb_dir=".kb")
            config.ensure_dirs()
            path = _hash_ledger_path(config)
            path.write_text(
                json.dumps({"oldhash": "aaaaaaaaaaaa"}, indent=1),
                encoding="utf-8",
            )

            def fail_replace(src, dst):
                raise OSError("replace failed")

            with patch("kb.pipeline.os.replace", side_effect=fail_replace):
                _save_hash_ledger(config, {"newhash": "bbbbbbbbbbbb"})

            self.assertEqual(_load_hash_ledger(config), {"oldhash": "aaaaaaaaaaaa"})
            self.assertFalse((path.parent / f".{path.name}.tmp").exists())


if __name__ == "__main__":
    unittest.main()
