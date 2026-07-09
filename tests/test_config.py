import os
import tempfile
import unittest
from pathlib import Path

from kb.config import ConfigError, load_config


class ConfigLoadingTests(unittest.TestCase):
    def setUp(self):
        self._cwd = Path.cwd()
        self._env = {
            key: value for key, value in os.environ.items() if key.startswith("KB_")
        }
        for key in self._env:
            os.environ.pop(key, None)

    def tearDown(self):
        os.chdir(self._cwd)
        for key in list(os.environ):
            if key.startswith("KB_"):
                os.environ.pop(key, None)
        os.environ.update(self._env)

    def test_invalid_boolean_reports_field_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            cfg = root / "kb.toml"
            cfg.write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        'rewrite_source_notes = "maybe"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["KB_CONFIG"] = str(cfg)

            with self.assertRaises(ConfigError) as raised:
                load_config()

            message = str(raised.exception)
            self.assertIn("Invalid boolean for rewrite_source_notes", message)
            self.assertIn("true/false", message)

    def test_invalid_integer_reports_field_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            cfg = root / "kb.toml"
            cfg.write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        'embed_dim = "wide"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["KB_CONFIG"] = str(cfg)

            with self.assertRaises(ConfigError) as raised:
                load_config()

            self.assertIn("Invalid integer for embed_dim", str(raised.exception))

    def test_invalid_toml_reports_config_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "kb.toml"
            cfg.write_text("vault_path = [", encoding="utf-8")
            os.environ["KB_CONFIG"] = str(cfg)

            with self.assertRaises(ConfigError) as raised:
                load_config()

            message = str(raised.exception)
            self.assertIn("Invalid TOML", message)
            self.assertIn(str(cfg), message)

    def test_missing_explicit_kb_config_does_not_fall_back_silently(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            (root / "kb.toml").write_text(
                f'vault_path = "{vault.as_posix()}"\n',
                encoding="utf-8",
            )
            missing = root / "missing.toml"
            os.environ["KB_CONFIG"] = str(missing)

            with self.assertRaises(ConfigError) as raised:
                load_config()

            self.assertIn("KB_CONFIG points to a missing file", str(raised.exception))
            self.assertIn(str(missing), str(raised.exception))

    def test_boolean_strings_are_coerced_explicitly(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            cfg = root / "kb.toml"
            cfg.write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        'zotero_enrich = "off"',
                        'references_by_subdomain = "yes"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["KB_CONFIG"] = str(cfg)

            config = load_config()

            self.assertFalse(config.zotero_enrich)
            self.assertTrue(config.references_by_subdomain)


if __name__ == "__main__":
    unittest.main()
