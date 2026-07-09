import unittest
from pathlib import Path

from kb.chunk import chunk_markdown
from kb.config import Config


class ChunkMarkdownTests(unittest.TestCase):
    def _config(self, *, chunk_size: int = 200, overlap: int = 20) -> Config:
        return Config(
            vault_path=Path("unused"),
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )

    def test_headers_inside_balanced_code_fences_are_not_sections(self):
        markdown = "\n".join(
            [
                "# Intro",
                "",
                "Opening text.",
                "",
                "```python",
                "# Not A Markdown Header",
                "print('hello')",
                "```",
                "",
                "## Method",
                "",
                "Real method body.",
            ]
        )

        chunks = chunk_markdown(markdown, self._config())

        self.assertEqual([c.header for c in chunks], ["Intro", "Intro > Method"])
        self.assertIn("# Not A Markdown Header", chunks[0].text)

    def test_unbalanced_code_fence_falls_back_to_header_splitting(self):
        markdown = "\n".join(
            [
                "# Intro",
                "",
                "```python",
                "print('unterminated')",
                "",
                "## Method",
                "",
                "This should still become its own section.",
            ]
        )

        chunks = chunk_markdown(markdown, self._config())

        self.assertEqual([c.header for c in chunks], ["Intro", "Intro > Method"])
        self.assertIn("unterminated", chunks[0].text)
        self.assertIn("This should still become", chunks[1].text)

    def test_long_sections_are_windowed_with_stable_indexes(self):
        markdown = "# Long\n\n" + " ".join(f"sentence{i}." for i in range(30))

        chunks = chunk_markdown(markdown, self._config(chunk_size=80, overlap=10))

        self.assertGreater(len(chunks), 1)
        self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))
        self.assertTrue(all(c.header == "Long" for c in chunks))
        self.assertTrue(all(len(c.text) <= 90 for c in chunks))


if __name__ == "__main__":
    unittest.main()
