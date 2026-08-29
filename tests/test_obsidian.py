import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kb.config import Config
from kb.models import Document, PaperAnalysis, PaperMetadata
from kb import obsidian


def _existing_note_text(my_notes: str) -> str:
    return (
        "---\n"
        "Date: 2026-07-10\n"
        "Type:\n"
        "- Paper\n"
        "kb-generated: true\n"
        "---\n"
        "# Existing Paper\n"
        "\n"
        "## TL;DR\n"
        "\n"
        "Old summary.\n"
        "\n"
        "## My Notes\n"
        "\n"
        f"{my_notes.rstrip()}\n"
        "\n"
        "---\n"
        "# References\n"
        "\n"
        "- Old reference\n"
    )


class ObsidianNoteTests(unittest.TestCase):
    def test_atomic_write_keeps_existing_note_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "note.md"
            path.write_text("original", encoding="utf-8")

            with patch("kb.obsidian.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    obsidian.write_text_atomic(path, "replacement")

            self.assertEqual(path.read_text(encoding="utf-8"), "original")
            self.assertFalse(list(path.parent.glob(f".{path.name}.*.tmp")))

    def test_sanitize_filename_is_windows_and_wikilink_safe(self):
        self.assertEqual(
            obsidian.sanitize_filename('CON: bad/name [draft]?', 2024),
            "CON bad name (draft) (2024)",
        )
        self.assertEqual(
            obsidian.sanitize_filename("A" * 160, None),
            "A" * 120,
        )
        self.assertEqual(obsidian.sanitize_filename("CON", None), "CON (concept)")
        self.assertEqual(obsidian.sanitize_filename("...", None), "Untitled")

    def test_split_frontmatter_uses_line_delimited_closing_marker(self):
        text = (
            "---\n"
            "tags:\n"
            "- computer-science---computer-vision\n"
            "source: https://example.org/a---b\n"
            "---\n"
            "# Body\n"
            "\n"
            "Text with --- inside the body.\n"
        )

        frontmatter, body = obsidian.split_frontmatter(text)

        self.assertIn("computer-science---computer-vision", frontmatter)
        self.assertIn("https://example.org/a---b", frontmatter)
        self.assertEqual(body, "# Body\n\nText with --- inside the body.\n")

    def test_split_frontmatter_returns_original_text_without_opening_marker(self):
        text = "# Plain Note\n\nNo YAML here.\n"

        frontmatter, body = obsidian.split_frontmatter(text)

        self.assertIsNone(frontmatter)
        self.assertEqual(body, text)

    def test_is_generated_note_parses_frontmatter_flags_conservatively(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cases = {
                "bool_true.md": ("true", True),
                "quoted_true.md": ('"true"', True),
                "quoted_false.md": ('"false"', False),
                "quoted_no.md": ('"no"', False),
                "one.md": ("1", True),
                "zero.md": ("0", False),
            }

            for name, (value, expected) in cases.items():
                with self.subTest(name=name):
                    note = root / name
                    note.write_text(
                        f"---\nkb-generated: {value}\n---\n# Note\n",
                        encoding="utf-8",
                    )

                    self.assertEqual(obsidian.is_generated_note(note), expected)

    def test_existing_my_notes_preserves_subheadings_and_horizontal_rules(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "Existing Paper.md"
            my_notes = "\n".join(
                [
                    "First personal observation.",
                    "",
                    "## Follow-up Question",
                    "",
                    "- Does this connect to my current experiment?",
                    "",
                    "---",
                    "",
                    "More notes after a horizontal rule.",
                ]
            )
            note.write_text(_existing_note_text(my_notes), encoding="utf-8")

            extracted = obsidian.extract_my_notes(note)

            self.assertEqual(extracted, my_notes)

    def test_render_note_keeps_existing_my_notes_across_rebuild(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            note = root / "References" / "Existing Paper (2024).md"
            note.parent.mkdir(parents=True)
            my_notes = "\n".join(
                [
                    "Keep this note.",
                    "",
                    "## My Subtopic",
                    "",
                    "A detail I wrote myself.",
                    "",
                    "---",
                    "",
                    "Another personal block.",
                ]
            )
            note.write_text(_existing_note_text(my_notes), encoding="utf-8")
            doc = Document(
                doc_id="abc123abc123",
                source_path=root / "paper.pdf",
                kind="pdf",
                markdown="",
                metadata=PaperMetadata(title="Existing Paper", year=2024),
                analysis=PaperAnalysis(tl_dr="Fresh generated summary."),
            )
            doc.note_path = note
            config = Config(vault_path=root, references_dir="References", kb_dir=".kb")

            rendered = obsidian.render_note(doc, ["Related Paper"], config)

            self.assertIn("## My Notes\n\n" + my_notes + "\n\n---\n# References", rendered)
            self.assertIn("Fresh generated summary.", rendered)
            self.assertNotIn("Old summary.", rendered)

    def test_metadata_classification_controls_location_and_frontmatter(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = Document(
                doc_id="abc123abc123",
                source_path=root / "paper.pdf",
                kind="pdf",
                markdown="",
                metadata=PaperMetadata(
                    title="Metadata Classified Paper",
                    year=2024,
                    primary_domain="HCI",
                    subdomain="Health & Wellbeing",
                ),
            )
            config = Config(vault_path=root, references_dir="References", kb_dir=".kb")

            obsidian.assign_note_location(doc, config)
            rendered = obsidian.render_note(doc, [], config)

            self.assertEqual(
                doc.note_path,
                root
                / "References"
                / "HCI"
                / "Health & Wellbeing"
                / "Metadata Classified Paper (2024).md",
            )
            self.assertIn("Domain: HCI", rendered)
            self.assertIn("Subdomain: Health & Wellbeing", rendered)

    def test_note_location_avoids_basename_collisions_anywhere_in_vault(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            existing = root / "6 - Knowledge Library" / "Shared Title (2024).md"
            existing.parent.mkdir(parents=True)
            existing.write_text("# A different note\n", encoding="utf-8")
            doc = Document(
                doc_id="abc123abc123",
                source_path=root / "paper.pdf",
                kind="pdf",
                markdown="",
                metadata=PaperMetadata(title="Shared Title", year=2024),
            )
            config = Config(vault_path=root, references_dir="References", kb_dir=".kb")

            obsidian.assign_note_location(doc, config)

            self.assertEqual(doc.link_target, "Shared Title (2024) (2)")

    def test_update_related_in_file_preserves_surrounding_user_content(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "User Note.md"
            note.write_text(
                "\n".join(
                    [
                        "# User Note",
                        "",
                        "Before block.",
                        "",
                        "## Related Papers",
                        "",
                        obsidian.RELATED_START,
                        "- [[Old Paper]]",
                        obsidian.RELATED_END,
                        "",
                        "After block.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            changed = obsidian.update_related_in_file(note, ["New Paper"])
            text = note.read_text(encoding="utf-8")

            self.assertTrue(changed)
            self.assertIn("Before block.", text)
            self.assertIn("After block.", text)
            self.assertIn("- [[New Paper]]", text)
            self.assertNotIn("Old Paper", text)

    def test_update_related_in_file_skips_duplicate_marker_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "User Note.md"
            original = "\n".join(
                [
                    "# User Note",
                    "",
                    "## Related Papers",
                    "",
                    obsidian.RELATED_START,
                    "- [[Old Paper One]]",
                    obsidian.RELATED_END,
                    "",
                    "Between blocks.",
                    "",
                    obsidian.RELATED_START,
                    "- [[Old Paper Two]]",
                    obsidian.RELATED_END,
                    "",
                ]
            )
            note.write_text(original, encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout):
                changed = obsidian.update_related_in_file(note, ["New Paper"])

            self.assertFalse(changed)
            self.assertIn("2 start marker(s) and 2 end marker(s)", stdout.getvalue())
            self.assertEqual(note.read_text(encoding="utf-8"), original)

    def test_update_related_in_file_skips_reversed_markers(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "User Note.md"
            original = "\n".join(
                [
                    "# User Note",
                    "",
                    obsidian.RELATED_END,
                    "- [[Old Paper]]",
                    obsidian.RELATED_START,
                    "",
                ]
            )
            note.write_text(original, encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout):
                changed = obsidian.update_related_in_file(note, ["New Paper"])

            self.assertFalse(changed)
            self.assertIn("markers out of order", stdout.getvalue())
            self.assertEqual(note.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
