"""Install a built wheel and exercise the public setup and legacy init CLIs."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path


def _venv_python(environment: Path) -> Path:
    relative = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    return environment / relative


def _venv_command(environment: Path, command: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    relative = f"Scripts/{command}{suffix}" if sys.platform == "win32" else f"bin/{command}"
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
        setup_work = root / "setup-work"
        legacy_work = root / "legacy-work"
        setup_vault = root / "setup-vault"
        legacy_vault = root / "legacy-vault"
        isolated_home = root / "home"
        isolated_appdata = root / "appdata"
        isolated_config = root / "config"
        isolated_home.mkdir()
        isolated_appdata.mkdir()
        isolated_config.mkdir()
        isolated_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("KB_")
        }
        isolated_env.update(
            {
                "HOME": str(isolated_home),
                "USERPROFILE": str(isolated_home),
                "APPDATA": str(isolated_appdata),
                "XDG_CONFIG_HOME": str(isolated_config),
            }
        )
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        paperroach = _venv_command(environment, "paperroach")
        subprocess.check_call([str(python), "-m", "pip", "install", "--no-deps", str(wheel)])
        setup_work.mkdir()
        legacy_work.mkdir()
        (setup_vault / ".obsidian").mkdir(parents=True)
        subprocess.check_call(
            [str(paperroach), "--version"],
            cwd=setup_work,
            env=isolated_env,
        )

        user_config = root / "user-config" / "kb.toml"
        setup_command = [
            str(paperroach),
            "setup",
            "--vault",
            str(setup_vault),
            "--config",
            str(user_config),
        ]
        subprocess.check_call(setup_command, cwd=setup_work, env=isolated_env)
        subprocess.check_call(setup_command, cwd=setup_work, env=isolated_env)
        setup_config = tomllib.loads(user_config.read_text(encoding="utf-8"))
        if Path(setup_config.get("vault_path", "")).resolve() != setup_vault.resolve():
            raise RuntimeError("Installed wheel setup wrote the wrong vault path.")
        if not (setup_vault / "References").is_dir() or not (
            setup_vault / ".kb"
        ).is_dir():
            raise RuntimeError("Installed wheel setup did not prepare vault folders.")

        subprocess.check_call(
            [str(paperroach), "init", "--vault", str(legacy_vault)],
            cwd=legacy_work,
            env=isolated_env,
        )
        config = tomllib.loads((legacy_work / "kb.toml").read_text(encoding="utf-8"))
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
