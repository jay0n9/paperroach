import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kb.config import Config
from kb.pipeline import PipelineLock, PipelineLockError, watch


class PipelineLockTests(unittest.TestCase):
    def _config(self, root: Path) -> Config:
        vault = root / "vault"
        vault.mkdir()
        return Config(vault_path=vault)

    def test_fresh_lock_blocks_second_writer(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._config(Path(td))
            with PipelineLock(config, "first") as lock:
                with self.assertRaises(PipelineLockError) as raised:
                    with PipelineLock(config, "second"):
                        pass

                self.assertIn("Another PaperRoach write command", str(raised.exception))
                self.assertTrue(lock.path.exists())

            self.assertFalse(lock.path.exists())

    def test_stale_lock_is_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._config(Path(td))
            lock_path = config.kb_path / "pipeline.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text(
                json.dumps({"owner": "old", "pid": 999, "token": "old"}),
                encoding="utf-8",
            )
            old_time = time.time() - 10
            os.utime(lock_path, (old_time, old_time))

            with PipelineLock(config, "new", stale_seconds=1) as lock:
                data = json.loads(lock.path.read_text(encoding="utf-8"))
                self.assertEqual(data["owner"], "new")

            self.assertFalse(lock_path.exists())

    def test_release_does_not_remove_another_owner_lock(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._config(Path(td))
            with PipelineLock(config, "first") as lock:
                lock.path.write_text(
                    json.dumps({"owner": "second", "pid": 123, "token": "second"}),
                    encoding="utf-8",
                )

            self.assertTrue(lock.path.exists())

    def test_automatic_heartbeat_keeps_a_long_running_lock_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._config(Path(td))
            with PipelineLock(
                config,
                "long-running",
                stale_seconds=0.1,
                heartbeat_interval=0.02,
            ):
                time.sleep(0.16)
                with self.assertRaises(PipelineLockError):
                    with PipelineLock(config, "second", stale_seconds=0.1):
                        pass

    def test_watcher_does_not_hold_writer_lock_between_polls(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root)
            zotero_dir = root / "zotero"
            zotero_dir.mkdir()
            acquired = []

            def interrupt_after_proving_lock_is_free(_seconds):
                with PipelineLock(config, "manual"):
                    acquired.append(True)
                raise KeyboardInterrupt

            with (
                redirect_stdout(StringIO()),
                patch("kb.pipeline.zotero.find_data_dir", return_value=zotero_dir),
                patch("kb.pipeline.zotero.storage_pdfs", return_value=[]),
                patch("kb.pipeline.time.sleep", side_effect=interrupt_after_proving_lock_is_free),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    watch(config)

            self.assertEqual(acquired, [True])


if __name__ == "__main__":
    unittest.main()
