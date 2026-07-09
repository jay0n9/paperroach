import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kb import knowledge
from kb.config import Config


def _write_generated_concept(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "Type:",
                "- Concept",
                "Subject: Computer Science",
                "Parent: []",
                "kb-generated: true",
                "---",
                f"# {path.stem}",
                "---",
                "",
                "Concept body.",
                "",
                "## Source",
                "",
                f"- From: [[{source}]]",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_generated_moc(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "---",
            "Type:",
            "- MOC",
            "Subject: Computer Science",
            "tags:",
            "- MOC",
            "kb-generated: true",
            "---",
            f"# {path.stem}",
            "",
            "%% kb-moc-start %%",
            "- [[Concept A]]",
            "%% kb-moc-end %%",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")
    return text


class KnowledgeTests(unittest.TestCase):
    def test_link_siblings_skips_generated_moc_notes(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td) / "vault", kb_dir=".kb")
            folder = config.knowledge_library_path / "Computer Science"
            concept_a = folder / "Concept A.md"
            concept_b = folder / "Concept B.md"
            moc = folder / "Computer Science MOC.md"
            _write_generated_concept(concept_a, "Shared Paper")
            _write_generated_concept(concept_b, "Shared Paper")
            original_moc = _write_generated_moc(moc)

            changed = knowledge.link_siblings(config)

            self.assertEqual(changed, 2)
            self.assertIn("Sibling:", concept_a.read_text(encoding="utf-8"))
            self.assertIn("[[Concept B]]", concept_a.read_text(encoding="utf-8"))
            self.assertEqual(moc.read_text(encoding="utf-8"), original_moc)

    def test_write_related_concepts_skips_duplicate_marker_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "Concept.md"
            original = "\n".join(
                [
                    "# Concept",
                    "",
                    "## Related Concepts",
                    "",
                    knowledge._RC_START,
                    "- [[Old One]]",
                    knowledge._RC_END,
                    "",
                    knowledge._RC_START,
                    "- [[Old Two]]",
                    knowledge._RC_END,
                    "",
                    "## Source",
                    "- From: [[Paper]]",
                    "",
                ]
            )
            note.write_text(original, encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout):
                changed = knowledge._write_related_concepts(note, ["New Concept"])

            self.assertFalse(changed)
            self.assertIn("2 start marker(s) and 2 end marker(s)", stdout.getvalue())
            self.assertEqual(note.read_text(encoding="utf-8"), original)

    def test_ensure_list_props_overwrites_case_variant_without_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "Paper.md"
            note.write_text(
                "\n".join(
                    [
                        "---",
                        "Status: Unread",
                        "Tags:",
                        "- paper",
                        "- old-tag",
                        "---",
                        "# Paper",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            changed = knowledge._ensure_list_props(
                note,
                [("tags", ["paper", "new-tag"], "Status")],
                overwrite=True,
            )

            self.assertTrue(changed)
            text = note.read_text(encoding="utf-8")
            self.assertIn("tags:\n- paper\n- new-tag", text)
            self.assertNotIn("Tags:", text)
            self.assertEqual(text.count("tags:"), 1)

    def test_append_source_link_adds_source_when_body_mentions_paper(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "Concept.md"
            note.write_text(
                "\n".join(
                    [
                        "# Concept",
                        "",
                        "The body mentions [[Paper One]] as context.",
                        "",
                        "## Source",
                        "- From: [[Other Paper]]",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            changed = knowledge._append_source_link(note, "Paper One")

            self.assertTrue(changed)
            text = note.read_text(encoding="utf-8")
            self.assertIn("The body mentions [[Paper One]] as context.", text)
            self.assertIn("- From: [[Paper One]]", text)

    def test_append_source_link_is_idempotent_for_source_alias(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "Concept.md"
            original = "\n".join(
                [
                    "# Concept",
                    "",
                    "## Source",
                    "- From: [[Paper One|alias]]",
                    "",
                ]
            )
            note.write_text(original, encoding="utf-8")

            changed = knowledge._append_source_link(note, "Paper One")

            self.assertFalse(changed)
            self.assertEqual(note.read_text(encoding="utf-8"), original)

    def test_write_related_concepts_skips_reversed_markers(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / "Concept.md"
            original = "\n".join(
                [
                    "# Concept",
                    "",
                    knowledge._RC_END,
                    "- [[Old Concept]]",
                    knowledge._RC_START,
                    "",
                ]
            )
            note.write_text(original, encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout):
                changed = knowledge._write_related_concepts(note, ["New Concept"])

            self.assertFalse(changed)
            self.assertIn("markers out of order", stdout.getvalue())
            self.assertEqual(note.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
