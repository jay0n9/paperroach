import tempfile
import unittest
import warnings
from pathlib import Path

from kb.config import Config
from kb.store import KBStore


class StoreTests(unittest.TestCase):
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
