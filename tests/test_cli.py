import os
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kb import __version__
from kb import cli
from kb.cli import build_parser, main
from kb.config import load_config


class CLITests(unittest.TestCase):
    def test_version_uses_public_project_name(self):
        stdout = StringIO()

        with self.assertRaises(SystemExit) as raised, redirect_stdout(stdout):
            build_parser().parse_args(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"paperroach {__version__}")

    def test_pyproject_version_matches_runtime_version(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

        self.assertEqual(data["project"]["version"], __version__)

    def test_init_command_writes_config_for_public_cli(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path.cwd()
            root = Path(td)
            vault = root / "vault"
            stdout = StringIO()
            try:
                os.chdir(root)
                with redirect_stdout(stdout):
                    code = main(["init", "--vault", str(vault)])
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 0)
            self.assertTrue((root / "kb.toml").exists())
            self.assertTrue((vault / "References").exists())
            self.assertIn("Wrote", stdout.getvalue())

    def test_config_warning_uses_public_project_name(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path.cwd()
            root = Path(td)
            vault = root / "vault"
            vault.mkdir()
            (root / "kb.toml").write_text(
                "\n".join(
                    [
                        f'vault_path = "{vault.as_posix()}"',
                        'unknown_option = "ignored"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            old_env = {
                key: value for key, value in os.environ.items() if key.startswith("KB_")
            }
            for key in old_env:
                os.environ.pop(key, None)
            stderr = StringIO()
            try:
                os.chdir(root)
                with redirect_stderr(stderr):
                    load_config()
            finally:
                os.chdir(cwd)
                os.environ.update(old_env)

            warning = stderr.getvalue()
            self.assertIn("paperroach: warning", warning)
            self.assertNotIn("kb: warning", warning)

    def test_build_command_returns_nonzero_when_nothing_succeeds(self):
        with patch.object(cli, "_config_from_args", return_value=object()):
            with patch("kb.pipeline.build", return_value={"processed": 0, "succeeded": []}):
                code = main(["build", "missing.pdf"])

        self.assertEqual(code, 1)

    def test_build_command_returns_zero_for_success_or_known_duplicates(self):
        cases = [
            {"processed": 1, "succeeded": ["doc123"]},
            {"processed": 0, "succeeded": [], "skipped_duplicates": ["doc456"]},
        ]

        for result in cases:
            with self.subTest(result=result):
                with patch.object(cli, "_config_from_args", return_value=object()):
                    with patch("kb.pipeline.build", return_value=result):
                        code = main(["build", "paper.pdf"])

                self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
