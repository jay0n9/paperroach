import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kb import tags
from kb.config import Config


class TagRegistryTests(unittest.TestCase):
    def test_save_registry_replaces_single_managed_block_and_preserves_prose(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td) / "vault", kb_dir=".kb")
            path = tags.registry_path(config)
            path.parent.mkdir(parents=True)
            path.write_text(
                "\n".join(
                    [
                        "# Tag Registry",
                        "",
                        "Before table.",
                        "",
                        tags.REGISTRY_START,
                        "| tag | description | aliases |",
                        "|---|---|---|",
                        "| old-tag | old | oldalias |",
                        tags.REGISTRY_END,
                        "",
                        "After table.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            tags.save_registry(
                config,
                {"new-tag": {"description": "New description", "aliases": ["newalias"]}},
            )
            text = path.read_text(encoding="utf-8")

            self.assertIn("Before table.", text)
            self.assertIn("After table.", text)
            self.assertIn("| new-tag | New description | newalias |", text)
            self.assertNotIn("old-tag", text)

    def test_save_registry_appends_block_to_existing_note_without_markers(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td) / "vault", kb_dir=".kb")
            path = tags.registry_path(config)
            path.parent.mkdir(parents=True)
            path.write_text("# My Tags\n\nHand written intro.\n", encoding="utf-8")

            tags.save_registry(
                config,
                {"paper-tag": {"description": "Reusable", "aliases": []}},
            )
            text = path.read_text(encoding="utf-8")

            self.assertTrue(text.startswith("# My Tags\n\nHand written intro."))
            self.assertIn(tags.REGISTRY_START, text)
            self.assertIn("| paper-tag | Reusable |  |", text)

    def test_save_registry_skips_duplicate_marker_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td) / "vault", kb_dir=".kb")
            path = tags.registry_path(config)
            path.parent.mkdir(parents=True)
            original = "\n".join(
                [
                    "# Tag Registry",
                    tags.REGISTRY_START,
                    "| tag | description | aliases |",
                    "|---|---|---|",
                    "| old-one |  |  |",
                    tags.REGISTRY_END,
                    tags.REGISTRY_START,
                    "| tag | description | aliases |",
                    "|---|---|---|",
                    "| old-two |  |  |",
                    tags.REGISTRY_END,
                    "",
                ]
            )
            path.write_text(original, encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout):
                tags.save_registry(
                    config,
                    {"new-tag": {"description": "", "aliases": []}},
                )

            self.assertIn("2 start marker(s) and 2 end marker(s)", stdout.getvalue())
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_save_registry_skips_reversed_markers(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td) / "vault", kb_dir=".kb")
            path = tags.registry_path(config)
            path.parent.mkdir(parents=True)
            original = "\n".join(
                [
                    "# Tag Registry",
                    tags.REGISTRY_END,
                    "| old |  |  |",
                    tags.REGISTRY_START,
                    "",
                ]
            )
            path.write_text(original, encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout):
                tags.save_registry(
                    config,
                    {"new-tag": {"description": "", "aliases": []}},
                )

            self.assertIn("markers out of order", stdout.getvalue())
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_load_registry_ignores_ambiguous_marker_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td) / "vault", kb_dir=".kb")
            path = tags.registry_path(config)
            path.parent.mkdir(parents=True)
            path.write_text(
                "\n".join(
                    [
                        tags.REGISTRY_START,
                        "| tag | description | aliases |",
                        "|---|---|---|",
                        "| one | first |  |",
                        tags.REGISTRY_END,
                        tags.REGISTRY_START,
                        "| tag | description | aliases |",
                        "|---|---|---|",
                        "| two | second |  |",
                        tags.REGISTRY_END,
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(tags.load_registry(config), {})


if __name__ == "__main__":
    unittest.main()
