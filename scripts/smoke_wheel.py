"""Install a built wheel in an isolated venv and exercise ``paperroach init``."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path


def _venv_python(environment: Path) -> Path:
    relative = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    return environment / relative


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel_dir", type=Path)
    args = parser.parse_args(argv)
    wheels = sorted(args.wheel_dir.glob("paperroach-*.whl"))
    if len(wheels) != 1:
        parser.error(f"Expected exactly one PaperRoach wheel in {args.wheel_dir}.")
    wheel = wheels[0].resolve()

    with tempfile.TemporaryDirectory(prefix="paperroach-wheel-smoke-") as td:
        root = Path(td)
        environment = root / "venv"
        work = root / "work"
        vault = root / "vault"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        subprocess.check_call([str(python), "-m", "pip", "install", "--no-deps", str(wheel)])
        work.mkdir()
        subprocess.check_call(
            [str(python), "-m", "paperroach", "init", "--vault", str(vault)],
            cwd=work,
        )
        config = tomllib.loads((work / "kb.toml").read_text(encoding="utf-8"))
        if (
            config.get("embed_dim") != 1024
            or config.get("ingester") != "pymupdf4llm"
            or config.get("figure_mode") != "off"
            or config.get("figure_backend") != "docling"
        ):
            raise RuntimeError("Installed wheel wrote an incomplete configuration template.")
    print(f"Wheel smoke test passed: {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
