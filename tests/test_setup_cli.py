import os
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kb import cli
from kb.cli import main
from kb.config import Config


class SetupCLITests(unittest.TestCase):
    def setUp(self):
        self._kb_env = {
            key: value for key, value in os.environ.items() if key.startswith("KB_")
        }
        for key in self._kb_env:
            os.environ.pop(key, None)

    def tearDown(self):
        for key in list(os.environ):
            if key.startswith("KB_"):
                os.environ.pop(key, None)
        os.environ.update(self._kb_env)

    @staticmethod
    def _vault(root: Path, name: str = "vault") -> Path:
        vault = root / name
        (vault / ".obsidian").mkdir(parents=True)
        return vault

    def test_setup_writes_user_config_and_prepares_vault(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = self._vault(root, "내 논문 vault")
            config_path = root / "user-config" / "kb.toml"
            stdout = StringIO()

            with patch("kb.zotero.find_data_dir", return_value=None):
                with redirect_stdout(stdout):
                    code = main(
                        [
                            "setup",
                            "--vault",
                            str(vault),
                            "--config",
                            str(config_path),
                        ]
                    )

            self.assertEqual(code, 0)
            with config_path.open("rb") as handle:
                payload = tomllib.load(handle)
            self.assertEqual(Path(payload["vault_path"]), vault)
            self.assertTrue((vault / "References").is_dir())
            self.assertTrue((vault / ".kb").is_dir())
            self.assertIn("[OK] Config", stdout.getvalue())
            self.assertIn("paperroach doctor", stdout.getvalue())

    def test_setup_auto_detects_one_vault_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = self._vault(root)
            config_path = root / "kb.toml"
            stdout = StringIO()

            with patch.object(
                cli, "discover_obsidian_vaults", return_value=[vault.resolve()]
            ):
                with patch("kb.zotero.find_data_dir", return_value=None):
                    with redirect_stdout(stdout):
                        first = main(["setup", "--config", str(config_path)])
                        second = main(["setup", "--config", str(config_path)])

            self.assertEqual((first, second), (0, 0))
            self.assertIn("Detected Obsidian vault", stdout.getvalue())
            self.assertIn("Kept", stdout.getvalue())

    def test_setup_requires_explicit_vault_in_noninteractive_session(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = self._vault(root, "first")
            second = self._vault(root, "second")
            stderr = StringIO()

            with patch.object(
                cli, "discover_obsidian_vaults", return_value=[first, second]
            ):
                with patch.object(cli.sys, "stdin", StringIO()):
                    with redirect_stderr(stderr):
                        code = main(["setup", "--config", str(root / "kb.toml")])

            self.assertEqual(code, 2)
            self.assertIn("Multiple Obsidian vaults", stderr.getvalue())
            self.assertIn("--vault PATH", stderr.getvalue())
            self.assertFalse((root / "kb.toml").exists())

    def test_setup_never_creates_a_mistyped_vault(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing = root / "typo"
            stderr = StringIO()

            with redirect_stderr(stderr):
                code = main(
                    [
                        "setup",
                        "--vault",
                        str(missing),
                        "--config",
                        str(root / "kb.toml"),
                    ]
                )

            self.assertEqual(code, 2)
            self.assertIn("does not exist", stderr.getvalue())
            self.assertFalse(missing.exists())

    def test_setup_pulls_models_only_when_requested(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = self._vault(root)

            with patch("kb.zotero.find_data_dir", return_value=None):
                with patch.object(
                    cli, "_pull_ollama_models", return_value=True
                ) as pull:
                    code = main(
                        [
                            "setup",
                            "--vault",
                            str(vault),
                            "--config",
                            str(root / "kb.toml"),
                            "--pull-models",
                        ]
                    )

            self.assertEqual(code, 0)
            pull.assert_called_once_with(["qwen3:8b", "bge-m3"])

    def test_doctor_reports_a_missing_required_model(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            config = Config(vault_path=vault)
            stdout = StringIO()

            with patch.object(cli, "_config_from_args", return_value=config):
                with patch("kb.zotero.find_data_dir", return_value=None):
                    with patch("kb.ollama_client.OllamaClient") as client_type:
                        client_type.return_value.installed_models.return_value = {
                            config.llm_model
                        }
                        with redirect_stdout(stdout):
                            code = main(["doctor"])

            self.assertEqual(code, 1)
            self.assertIn("[OK] Text model", stdout.getvalue())
            self.assertIn("[FAIL] Embed model", stdout.getvalue())
            self.assertIn("ollama pull bge-m3", stdout.getvalue())

    def test_doctor_accepts_required_models(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            config = Config(vault_path=vault)
            stdout = StringIO()

            with patch.object(cli, "_config_from_args", return_value=config):
                with patch("kb.zotero.find_data_dir", return_value=None):
                    with patch("kb.ollama_client.OllamaClient") as client_type:
                        client_type.return_value.installed_models.return_value = {
                            config.llm_model,
                            config.embed_model,
                        }
                        with redirect_stdout(stdout):
                            code = main(["doctor"])

            self.assertEqual(code, 0)
            self.assertIn("[OK] Text model", stdout.getvalue())
            self.assertIn("[OK] Embed model", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
