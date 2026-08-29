import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb.config import load_config, user_config_path


class UserConfigTests(unittest.TestCase):
    def setUp(self):
        self._cwd = Path.cwd()
        self._saved_env = {
            key: value for key, value in os.environ.items() if key.startswith("KB_")
        }
        for key in self._saved_env:
            os.environ.pop(key, None)

    def tearDown(self):
        os.chdir(self._cwd)
        for key in list(os.environ):
            if key.startswith("KB_"):
                os.environ.pop(key, None)
        os.environ.update(self._saved_env)

    def test_user_config_path_is_platform_appropriate(self):
        home = Path("/home/alex")

        self.assertEqual(
            user_config_path(
                platform="win32",
                environ={"APPDATA": "C:/Users/alex/AppData/Roaming"},
                home=home,
            ),
            Path("C:/Users/alex/AppData/Roaming") / "PaperRoach" / "kb.toml",
        )
        self.assertEqual(
            user_config_path(platform="darwin", environ={}, home=home),
            home
            / "Library"
            / "Application Support"
            / "PaperRoach"
            / "kb.toml",
        )
        self.assertEqual(
            user_config_path(
                platform="linux",
                environ={"XDG_CONFIG_HOME": "/tmp/config"},
                home=home,
            ),
            Path("/tmp/config") / "paperroach" / "kb.toml",
        )

    def test_user_config_is_the_final_file_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            work = root / "work"
            config_path = root / "config" / "kb.toml"
            vault.mkdir()
            work.mkdir()
            config_path.parent.mkdir()
            config_path.write_text(
                f'vault_path = "{vault.as_posix()}"\nllm_model = "user-model"\n',
                encoding="utf-8",
            )

            with patch("kb.config.user_config_path", return_value=config_path):
                try:
                    os.chdir(work)
                    config = load_config()
                finally:
                    os.chdir(self._cwd)

            self.assertEqual(config.vault_path, vault)
            self.assertEqual(config.llm_model, "user-model")

    def test_working_directory_config_wins_over_user_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            user_vault = root / "user-vault"
            local_vault = root / "local-vault"
            work = root / "work"
            user_config = root / "config" / "kb.toml"
            user_vault.mkdir()
            local_vault.mkdir()
            work.mkdir()
            user_config.parent.mkdir()
            user_config.write_text(
                f'vault_path = "{user_vault.as_posix()}"\n',
                encoding="utf-8",
            )
            (work / "kb.toml").write_text(
                f'vault_path = "{local_vault.as_posix()}"\n',
                encoding="utf-8",
            )

            with patch("kb.config.user_config_path", return_value=user_config):
                try:
                    os.chdir(work)
                    config = load_config()
                finally:
                    os.chdir(self._cwd)

            self.assertEqual(config.vault_path, local_vault)

    def test_explicit_config_path_is_used_outside_the_working_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            work = root / "work"
            config_path = root / "chosen" / "kb.toml"
            vault.mkdir()
            work.mkdir()
            config_path.parent.mkdir()
            config_path.write_text(
                f'vault_path = "{vault.as_posix()}"\n',
                encoding="utf-8",
            )
            try:
                os.chdir(work)
                config = load_config(config_path=config_path)
            finally:
                os.chdir(self._cwd)

            self.assertEqual(config.vault_path, vault)


if __name__ == "__main__":
    unittest.main()
