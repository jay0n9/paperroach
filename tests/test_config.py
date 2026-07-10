import os
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
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

    def test_invalid_semantic_values_fail_before_pipeline_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            cfg = root / "kb.toml"
            cfg.write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        "chunk_size = 0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["KB_CONFIG"] = str(cfg)

            with self.assertRaises(ConfigError) as raised:
                load_config()

            self.assertIn("chunk_size must be at least 1", str(raised.exception))

    def test_overlap_must_be_smaller_than_chunk_size(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            cfg = root / "kb.toml"
            cfg.write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        "chunk_size = 100",
                        "chunk_overlap = 100",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["KB_CONFIG"] = str(cfg)

            with self.assertRaises(ConfigError) as raised:
                load_config()

            self.assertIn("chunk_overlap must be smaller", str(raised.exception))

    def test_output_directories_must_stay_inside_vault(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            cfg = root / "kb.toml"
            cfg.write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        'references_dir = "../outside"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["KB_CONFIG"] = str(cfg)

            with self.assertRaises(ConfigError) as raised:
                load_config()

            self.assertIn("references_dir must be a relative path", str(raised.exception))

    def test_embed_dim_environment_override_is_coerced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            os.environ["KB_VAULT"] = str(vault)
            os.environ["KB_EMBED_DIM"] = "3"

            try:
                os.chdir(root)
                config = load_config()
            finally:
                os.chdir(self._cwd)

            self.assertEqual(config.embed_dim, 3)

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

    def test_vault_override_ignores_cwd_config_for_different_vault(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            main_vault = root / "main-vault"
            other_vault = root / "other-vault"
            external_store = root / "external-store"
            main_vault.mkdir()
            other_vault.mkdir()
            (root / "kb.toml").write_text(
                "\n".join(
                    [
                        f'vault_path = "{main_vault.as_posix()}"',
                        f'kb_dir = "{external_store.as_posix()}"',
                        'llm_model = "custom-model"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            stderr = StringIO()
            try:
                os.chdir(root)
                with redirect_stderr(stderr):
                    config = load_config({"vault_path": str(other_vault)})
            finally:
                os.chdir(self._cwd)

            self.assertEqual(config.vault_path, other_vault)
            self.assertEqual(config.kb_dir, ".kb")
            self.assertEqual(config.llm_model, "qwen3:8b")
            self.assertIn("ignoring", stderr.getvalue())
            self.assertIn("kb.toml", stderr.getvalue())

    def test_kb_vault_ignores_cwd_config_for_different_vault(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            main_vault = root / "main-vault"
            other_vault = root / "other-vault"
            main_vault.mkdir()
            other_vault.mkdir()
            (root / "kb.toml").write_text(
                "\n".join(
                    [
                        f'vault_path = "{main_vault.as_posix()}"',
                        'llm_model = "custom-model"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["KB_VAULT"] = str(other_vault)

            stderr = StringIO()
            try:
                os.chdir(root)
                with redirect_stderr(stderr):
                    config = load_config()
            finally:
                os.chdir(self._cwd)

            self.assertEqual(config.vault_path, other_vault)
            self.assertEqual(config.llm_model, "qwen3:8b")
            self.assertIn("ignoring", stderr.getvalue())

    def test_kb_config_forces_specific_config_even_when_vault_differs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            configured_vault = root / "configured-vault"
            override_vault = root / "override-vault"
            configured_vault.mkdir()
            override_vault.mkdir()
            cfg = root / "explicit.toml"
            cfg.write_text(
                "\n".join(
                    [
                        f'vault_path = "{configured_vault.as_posix()}"',
                        'llm_model = "forced-model"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["KB_CONFIG"] = str(cfg)

            stderr = StringIO()
            with redirect_stderr(stderr):
                config = load_config({"vault_path": str(override_vault)})

            self.assertEqual(config.vault_path, override_vault)
            self.assertEqual(config.llm_model, "forced-model")
            self.assertNotIn("ignoring", stderr.getvalue())

    def test_vault_override_keeps_cwd_config_for_same_vault(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            (root / "kb.toml").write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        'llm_model = "custom-model"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            try:
                os.chdir(root)
                config = load_config({"vault_path": str(vault)})
            finally:
                os.chdir(self._cwd)

            self.assertEqual(config.vault_path, vault)
            self.assertEqual(config.llm_model, "custom-model")

    def test_vault_local_config_wins_over_cwd_config_when_vault_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cwd_vault = root / "cwd-vault"
            target_vault = root / "target-vault"
            cwd_vault.mkdir()
            target_vault.mkdir()
            (root / "kb.toml").write_text(
                "\n".join(
                    [
                        f'vault_path = "{cwd_vault.as_posix()}"',
                        'llm_model = "cwd-model"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (target_vault / "kb.toml").write_text(
                "\n".join(
                    [
                        f'vault_path = "{target_vault.as_posix()}"',
                        'llm_model = "vault-model"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            try:
                os.chdir(root)
                config = load_config({"vault_path": str(target_vault)})
            finally:
                os.chdir(self._cwd)

            self.assertEqual(config.vault_path, target_vault)
            self.assertEqual(config.llm_model, "vault-model")

    def test_figure_configuration_is_validated_and_assets_stay_in_vault(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()

            config = load_config(
                {
                    "vault_path": str(vault),
                    "figure_mode": "describe",
                    "vision_model": "qwen2.5vl:7b",
                    "figure_assets_dir": "Assets/PaperRoach",
                }
            )

            self.assertEqual(config.figure_mode, "describe")
            self.assertEqual(config.figure_assets_path, vault / "Assets" / "PaperRoach")

            with self.assertRaises(ConfigError) as invalid_mode:
                load_config({"vault_path": str(vault), "figure_mode": "all"})
            self.assertIn("Unknown figure_mode", str(invalid_mode.exception))

            with self.assertRaises(ConfigError) as outside_assets:
                load_config(
                    {
                        "vault_path": str(vault),
                        "figure_assets_dir": "../outside",
                    }
                )
            self.assertIn("figure_assets_dir must be a relative path", str(outside_assets.exception))


if __name__ == "__main__":
    unittest.main()
