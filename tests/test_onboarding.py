import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from kb.config import ConfigError
from kb.onboarding import (
    discover_obsidian_vaults,
    minimal_config,
    validate_obsidian_vault,
    write_user_config,
)


class OnboardingTests(unittest.TestCase):
    def _vault(self, root: Path, name: str) -> Path:
        vault = root / name
        (vault / ".obsidian").mkdir(parents=True)
        return vault

    def test_discovers_recent_open_vaults_and_ignores_invalid_entries(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = self._vault(root, "첫 번째 vault")
            second = self._vault(root, "second vault")
            config = root / "obsidian.json"
            config.write_text(
                json.dumps(
                    {
                        "vaults": {
                            "a": {"path": str(first), "ts": 10},
                            "b": {"path": str(second), "ts": 5, "open": True},
                            "missing": {"path": str(root / "missing"), "ts": 99},
                            "invalid-type": {"path": ["not", "a", "path"]},
                            "duplicate": {"path": str(first), "ts": 1},
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            work = root / "work"
            work.mkdir()

            found = discover_obsidian_vaults(
                cwd=work,
                environ={},
                config_paths=[config],
            )

            self.assertEqual(found, [second.resolve(), first.resolve()])

    def test_discovers_vault_from_current_directory_ancestor(self):
        with tempfile.TemporaryDirectory() as td:
            vault = self._vault(Path(td), "vault")
            nested = vault / "notes" / "drafts"
            nested.mkdir(parents=True)

            found = discover_obsidian_vaults(
                cwd=nested,
                environ={},
                config_paths=[],
            )

            self.assertEqual(found, [vault.resolve()])

    def test_malformed_obsidian_json_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            malformed = root / "obsidian.json"
            malformed.write_text("{broken", encoding="utf-8")

            found = discover_obsidian_vaults(
                cwd=root,
                environ={},
                config_paths=[malformed],
            )

            self.assertEqual(found, [])

    def test_validation_never_creates_or_accepts_a_plain_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing = root / "typo"
            plain = root / "plain"
            plain.mkdir()

            with self.assertRaisesRegex(ConfigError, "does not exist"):
                validate_obsidian_vault(missing)
            with self.assertRaisesRegex(ConfigError, "missing .obsidian"):
                validate_obsidian_vault(plain)

            self.assertFalse(missing.exists())

    def test_user_config_write_is_minimal_idempotent_and_force_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = self._vault(root, "first")
            second = self._vault(root, "second")
            config = root / "config" / "kb.toml"

            self.assertTrue(write_user_config(first, config))
            self.assertFalse(write_user_config(first, config))
            with config.open("rb") as handle:
                payload = tomllib.load(handle)
            self.assertEqual(Path(payload["vault_path"]), first)
            self.assertNotIn("llm_model", payload)

            with self.assertRaisesRegex(ConfigError, "--force"):
                write_user_config(second, config)
            self.assertEqual(
                config.read_text(encoding="utf-8"),
                minimal_config(first),
            )

            self.assertTrue(write_user_config(second, config, force=True))
            with config.open("rb") as handle:
                replaced = tomllib.load(handle)
            self.assertEqual(Path(replaced["vault_path"]), second)
            self.assertEqual(list(config.parent.glob(".kb.toml.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
