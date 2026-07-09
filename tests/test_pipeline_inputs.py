import tempfile
import unittest
from pathlib import Path

from kb.config import Config
from kb.pipeline import collect_inputs


def _write(path: Path, text: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class PipelineInputTests(unittest.TestCase):
    def test_collect_inputs_matches_supported_suffixes_case_insensitively(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            source = root / "source"
            config = Config(vault_path=vault, kb_dir=".kb")
            _write(source / "Paper.PDF")
            _write(source / "Note.MD")
            _write(source / "Ignored.txt")
            _write(source / "nested" / "Nested.MarkDown")
            _write(config.kb_path / "internal.PDF")
            generated = source / "Generated.MD"
            _write(
                generated,
                "\n".join(["---", "kb-generated: true", "---", "# Generated", ""]),
            )
            user_note = source / "UserNote.MD"
            _write(
                user_note,
                "\n".join(["---", 'kb-generated: "false"', "---", "# User note", ""]),
            )

            top_level = collect_inputs([source], config, recursive=False)
            recursive = collect_inputs([source, config.kb_path], config, recursive=True)

            self.assertEqual(
                {p.name for p in top_level},
                {"Paper.PDF", "Note.MD", "UserNote.MD"},
            )
            self.assertEqual(
                {p.name for p in recursive},
                {"Paper.PDF", "Note.MD", "Nested.MarkDown", "UserNote.MD"},
            )


if __name__ == "__main__":
    unittest.main()
