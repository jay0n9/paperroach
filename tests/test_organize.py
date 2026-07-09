import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kb import organize


def _moc_path(folder: Path) -> Path:
    return folder / f"{organize.MOC_PREFIX}{folder.name}{organize.MOC_SUFFIX}.md"


def _write_moc(folder: Path, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = _moc_path(folder)
    path.write_text(body, encoding="utf-8")
    return path


class OrganizeTests(unittest.TestCase):
    def test_write_moc_replaces_single_managed_block(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Computer Science"
            moc = _write_moc(
                folder,
                "\n".join(
                    [
                        "# Computer Science",
                        "",
                        "Before block.",
                        "",
                        organize._MOC_START,
                        "- [[Old Note]]",
                        organize._MOC_END,
                        "",
                        "After block.",
                        "",
                    ]
                ),
            )

            changed = organize._write_moc(folder, ["New Note"], [])
            text = moc.read_text(encoding="utf-8")

            self.assertTrue(changed)
            self.assertIn("Before block.", text)
            self.assertIn("After block.", text)
            self.assertIn("- [[New Note]]", text)
            self.assertNotIn("Old Note", text)

    def test_write_moc_skips_duplicate_marker_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Computer Science"
            original = "\n".join(
                [
                    "# Computer Science",
                    "",
                    organize._MOC_START,
                    "- [[Old One]]",
                    organize._MOC_END,
                    "",
                    organize._MOC_START,
                    "- [[Old Two]]",
                    organize._MOC_END,
                    "",
                ]
            )
            moc = _write_moc(folder, original)

            stdout = StringIO()
            with redirect_stdout(stdout):
                changed = organize._write_moc(folder, ["New Note"], [])

            self.assertFalse(changed)
            self.assertIn("2 start marker(s) and 2 end marker(s)", stdout.getvalue())
            self.assertEqual(moc.read_text(encoding="utf-8"), original)

    def test_write_moc_skips_reversed_markers(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Computer Science"
            original = "\n".join(
                [
                    "# Computer Science",
                    "",
                    organize._MOC_END,
                    "- [[Old Note]]",
                    organize._MOC_START,
                    "",
                ]
            )
            moc = _write_moc(folder, original)

            stdout = StringIO()
            with redirect_stdout(stdout):
                changed = organize._write_moc(folder, ["New Note"], [])

            self.assertFalse(changed)
            self.assertIn("markers out of order", stdout.getvalue())
            self.assertEqual(moc.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
