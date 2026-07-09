import os
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kb import __version__
from kb import cli
from kb.cli import build_parser, main
from kb.config import Config, load_config
from kb.store import KBStore


class CLITests(unittest.TestCase):
    def _temp_config(self, root: Path) -> Config:
        vault = root / "vault"
        vault.mkdir()
        return Config(vault_path=vault)

    def test_version_uses_public_project_name(self):
        stdout = StringIO()

        with self.assertRaises(SystemExit) as raised, redirect_stdout(stdout):
            build_parser().parse_args(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"paperroach {__version__}")

    def test_embed_dim_cli_override(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path.cwd()
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            try:
                os.chdir(root)
                args = build_parser().parse_args(
                    ["stats", "--vault", str(vault), "--embed-dim", "3"]
                )
                config = cli._config_from_args(args)
            finally:
                os.chdir(cwd)

            self.assertEqual(config.embed_dim, 3)

    def test_pyproject_version_matches_runtime_version(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

        self.assertEqual(data["project"]["version"], __version__)

    def test_init_command_writes_config_for_public_cli(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path.cwd()
            root = Path(td)
            vault = root / "vault"
            stdout = StringIO()
            try:
                os.chdir(root)
                with redirect_stdout(stdout):
                    code = main(["init", "--vault", str(vault)])
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 0)
            config_path = root / "kb.toml"
            self.assertTrue(config_path.exists())
            config_data = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config_data["embed_dim"], 1024)
            self.assertEqual(config_data["ingester"], "pymupdf4llm")
            self.assertTrue((vault / "References").exists())
            self.assertIn("Wrote", stdout.getvalue())

    def test_config_warning_uses_public_project_name(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path.cwd()
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            (root / "kb.toml").write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        'unknown_option = "ignored"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            old_env = {
                key: value for key, value in os.environ.items() if key.startswith("KB_")
            }
            for key in old_env:
                os.environ.pop(key, None)
            stderr = StringIO()
            try:
                os.chdir(root)
                with redirect_stderr(stderr):
                    load_config()
            finally:
                os.chdir(cwd)
                os.environ.update(old_env)

            warning = stderr.getvalue()
            self.assertIn("paperroach: warning", warning)
            self.assertNotIn("kb: warning", warning)

    def test_build_command_returns_nonzero_when_nothing_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._temp_config(Path(td))
            with patch.object(cli, "_config_from_args", return_value=config):
                with patch(
                    "kb.pipeline.build",
                    return_value={"processed": 0, "succeeded": []},
                ):
                    code = main(["build", "missing.pdf"])

        self.assertEqual(code, 1)

    def test_build_command_returns_zero_for_success_or_known_duplicates(self):
        cases = [
            {"processed": 1, "succeeded": ["doc123"]},
            {"processed": 0, "succeeded": [], "skipped_duplicates": ["doc456"]},
        ]

        for result in cases:
            with self.subTest(result=result):
                with tempfile.TemporaryDirectory() as td:
                    config = self._temp_config(Path(td))
                    with patch.object(cli, "_config_from_args", return_value=config):
                        with patch("kb.pipeline.build", return_value=result):
                            code = main(["build", "paper.pdf"])

                self.assertEqual(code, 0)

    def test_build_command_returns_locked_when_pipeline_lock_is_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._temp_config(Path(td))
            config.kb_path.mkdir(parents=True)
            (config.kb_path / "pipeline.lock").write_text(
                '{"owner": "other", "pid": 123, "token": "abc"}',
                encoding="utf-8",
            )
            stderr = StringIO()
            with patch.object(cli, "_config_from_args", return_value=config):
                with patch("kb.pipeline.build") as build_mock:
                    with redirect_stderr(stderr):
                        code = main(["build", "paper.pdf"])

            self.assertEqual(code, 3)
            build_mock.assert_not_called()
            self.assertIn("Another PaperRoach write command", stderr.getvalue())

    def test_doctor_reports_warnings_but_succeeds_for_empty_vault(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._temp_config(Path(td))
            stdout = StringIO()
            with patch.object(cli, "_config_from_args", return_value=config):
                with patch("kb.zotero.find_data_dir", return_value=None):
                    with redirect_stdout(stdout):
                        code = main(["doctor", "--skip-ollama"])

            output = stdout.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("[OK] Version", output)
            self.assertIn("[WARN] Store", output)
            self.assertIn("[WARN] Ollama", output)
            self.assertIn("Summary: 0 failure(s)", output)
            self.assertFalse(config.kb_path.exists())

    def test_stats_does_not_initialize_empty_store(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._temp_config(Path(td))
            stdout = StringIO()
            with patch.object(cli, "_config_from_args", return_value=config):
                with redirect_stdout(stdout):
                    code = main(["stats"])

            output = stdout.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("Documents   : 0", output)
            self.assertIn("Chunks      : 0", output)
            self.assertFalse(config.kb_path.exists())

    def test_stats_fails_on_store_embedding_model_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            first = Config(
                vault_path=vault,
                kb_dir=".kb",
                embed_model="first",
                embed_dim=3,
            )
            KBStore(first)
            changed = Config(
                vault_path=vault,
                kb_dir=".kb",
                embed_model="second",
                embed_dim=3,
            )
            stderr = StringIO()
            with patch.object(cli, "_config_from_args", return_value=changed):
                with redirect_stderr(stderr):
                    code = main(["stats"])

            self.assertEqual(code, 1)
            self.assertIn("embed_model='first'", stderr.getvalue())

    def test_gc_apply_does_not_initialize_empty_store(self):
        with tempfile.TemporaryDirectory() as td:
            config = self._temp_config(Path(td))
            stdout = StringIO()
            with patch.object(cli, "_config_from_args", return_value=config):
                with redirect_stdout(stdout):
                    code = main(["gc", "--apply"])

            self.assertEqual(code, 0)
            self.assertIn("Store is not initialized", stdout.getvalue())
            self.assertFalse(config.kb_path.exists())

    def test_doctor_fails_on_store_embedding_model_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            first = Config(
                vault_path=vault,
                kb_dir=".kb",
                embed_model="first",
                embed_dim=3,
            )
            KBStore(first)
            changed = Config(
                vault_path=vault,
                kb_dir=".kb",
                embed_model="second",
                embed_dim=3,
            )
            stdout = StringIO()
            with patch.object(cli, "_config_from_args", return_value=changed):
                with patch("kb.zotero.find_data_dir", return_value=None):
                    with redirect_stdout(stdout):
                        code = main(["doctor", "--skip-ollama"])

            output = stdout.getvalue()
            self.assertEqual(code, 1)
            self.assertIn("[FAIL] Store", output)
            self.assertIn("embed_model='first'", output)


if __name__ == "__main__":
    unittest.main()
