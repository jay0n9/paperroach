import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kb import obsidian
from kb.config import Config
from kb.pipeline import refile_references


def _refile_quietly(*args, **kwargs):
    with redirect_stdout(StringIO()):
        return refile_references(*args, **kwargs)


def _write_generated_note(
    path: Path,
    *,
    tags: list[str],
    body: str = "A compact test note.",
    extra_frontmatter: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tag_lines = "\n".join(f"- {tag}" for tag in tags)
    path.write_text(
        "\n".join(
            [
                "---",
                "Date: 2026-07-10",
                "Type:",
                "- Paper",
                "Status: Unread",
                "Authors: Test Author",
                "Year: 2024",
                "Source: https://example.org/paper",
                *(extra_frontmatter or []),
                "tags:",
                tag_lines,
                "kb-generated: true",
                "kb-source: C:/papers/test.pdf",
                "kb-doc-id: abc123abc123",
                "---",
                "# Test Paper",
                "",
                "## TL;DR",
                "",
                body,
            ]
        )
        + "\n",
        encoding="utf-8",
    )


class RefilePlanTests(unittest.TestCase):
    def test_refile_plan_is_written_without_moving_notes(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            cfg = Config(vault_path=vault, references_dir="References", kb_dir=".kb")
            note = cfg.references_path / "Test Paper (2024).md"
            _write_generated_note(note, tags=["paper", "computer-graphics", "neural-network"])
            plan = Path(td) / "refile-plan.md"

            result = _refile_quietly(cfg, apply=False, plan_out=plan)

            self.assertEqual(result["moved"], 0)
            self.assertEqual(result["planned"], 1)
            self.assertTrue(note.exists())
            text = plan.read_text(encoding="utf-8")
            self.assertIn("Computer Science/Computer Graphics/Test Paper (2024).md", text)
            self.assertIn("| move |", text)
            self.assertIn("| metadata |", text)

    def test_refile_apply_persists_inferred_frontmatter(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            cfg = Config(vault_path=vault, references_dir="References", kb_dir=".kb")
            note = cfg.references_path / "Test Paper (2024).md"
            _write_generated_note(note, tags=["paper", "computer-graphics", "neural-network"])
            plan = Path(td) / "refile-plan.md"

            result = _refile_quietly(cfg, apply=True, plan_out=plan)

            moved = (
                cfg.references_path
                / "Computer Science"
                / "Computer Graphics"
                / "Test Paper (2024).md"
            )
            self.assertEqual(result["moved"], 1)
            self.assertTrue(moved.exists())
            fm = obsidian._read_frontmatter(moved)
            self.assertEqual(fm["Domain"], "Computer Science")
            self.assertEqual(fm["Subdomain"], "Computer Graphics")
            self.assertIn("Applied moves: 1", plan.read_text(encoding="utf-8"))

    def test_metadata_subdomain_beats_body_terms(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            cfg = Config(vault_path=vault, references_dir="References", kb_dir=".kb")
            note = cfg.references_path / "Test Paper (2024).md"
            _write_generated_note(
                note,
                tags=["paper", "computer-graphics", "neural-network"],
                body=(
                    "This paragraph mentions multiple testing, false discovery rate, "
                    "statistical inference, correlations, and meta-analysis."
                ),
            )
            plan = Path(td) / "refile-plan.md"

            result = _refile_quietly(cfg, apply=False, plan_out=plan)

            self.assertEqual(result["planned"], 1)
            text = plan.read_text(encoding="utf-8")
            self.assertIn("Computer Science/Computer Graphics/Test Paper (2024).md", text)
            self.assertIn("| metadata |", text)

    def test_metadata_subdomain_beats_existing_domain_frontmatter(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            cfg = Config(vault_path=vault, references_dir="References", kb_dir=".kb")
            note = cfg.references_path / "Test Paper (2024).md"
            _write_generated_note(
                note,
                tags=["paper", "computer-graphics", "neural-network"],
                extra_frontmatter=["Domain: HCI"],
                body="The body talks about user studies and qualitative interviews.",
            )
            plan = Path(td) / "refile-plan.md"

            result = _refile_quietly(cfg, apply=False, plan_out=plan)

            self.assertEqual(result["planned"], 1)
            text = plan.read_text(encoding="utf-8")
            self.assertIn("Computer Science/Computer Graphics/Test Paper (2024).md", text)
            self.assertIn("| metadata |", text)

    def test_scalar_frontmatter_tags_are_metadata_signal(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            cfg = Config(vault_path=vault, references_dir="References", kb_dir=".kb")
            note = cfg.references_path / "Scalar Tag Paper (2024).md"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(
                "\n".join(
                    [
                        "---",
                        "Date: 2026-07-10",
                        "Type:",
                        "- Paper",
                        "Status: Unread",
                        "Authors: Test Author",
                        "Year: 2024",
                        "Source: https://example.org/paper",
                        "tags: computer-graphics",
                        "kb-generated: true",
                        "kb-source: C:/papers/scalar.pdf",
                        "kb-doc-id: scalar123",
                        "---",
                        "# Scalar Tag Paper",
                        "",
                        "## TL;DR",
                        "",
                        "The body mentions interviews and qualitative coding.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            plan = Path(td) / "refile-plan.md"

            result = _refile_quietly(cfg, apply=False, plan_out=plan)

            self.assertEqual(result["planned"], 1)
            text = plan.read_text(encoding="utf-8")
            self.assertIn("Computer Science/Computer Graphics/Scalar Tag Paper (2024).md", text)
            self.assertIn("| metadata |", text)


if __name__ == "__main__":
    unittest.main()
