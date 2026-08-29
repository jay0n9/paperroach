"""Command-line interface.

    paperroach setup                discover Obsidian and configure first run
    paperroach init                 scaffold a legacy local kb.toml
    paperroach build <paths...>     run the full pipeline (PASS A → swap → PASS B)
    paperroach enrich-figures       add visual evidence to existing paper notes
    paperroach integrate-figures    weave indexed figures into existing study notes
    paperroach search "<query>"     semantic search over chunks
    paperroach ask "<query>"        RAG answer grounded in your library
    paperroach relink               recompute related-literature wikilinks
    paperroach stats                show store statistics
    paperroach doctor               check local configuration and dependencies
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from kb import __version__
from kb.config import Config, ConfigError, load_config, user_config_path
from kb.onboarding import (
    discover_obsidian_vaults,
    validate_obsidian_vault,
    write_user_config,
)


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--vault", dest="vault_path", help="Path to the Obsidian vault")
    p.add_argument("--references-dir", dest="references_dir", help="Output subfolder")
    p.add_argument("--llm-model", dest="llm_model", help="Ollama LLM model tag")
    p.add_argument("--embed-model", dest="embed_model", help="Ollama embedding model")
    p.add_argument(
        "--embed-dim", dest="embed_dim", type=int, help="Embedding vector dimension"
    )
    p.add_argument("--ollama-host", dest="ollama_host", help="Ollama base URL")
    p.add_argument(
        "--figure-mode",
        dest="figure_mode",
        choices=("off", "extract", "describe"),
        help="PDF figure handling: off | extract | describe (vision model)",
    )
    p.add_argument(
        "--figure-backend",
        dest="figure_backend",
        choices=("docling", "pymupdf"),
        help="Figure extractor: docling (layout-aware) | pymupdf (offline raster)",
    )
    p.add_argument("--vision-model", dest="vision_model", help="Ollama vision model tag")
    p.add_argument(
        "--figure-assets-dir",
        dest="figure_assets_dir",
        help="Vault-relative directory for extracted figure images",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperroach",
        description=(
            "PaperRoach: local-first paper knowledge pipeline "
            "(Obsidian, Zotero, Ollama, LanceDB)."
        ),
    )
    parser.add_argument("--version", action="version", version=f"paperroach {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_setup = sub.add_parser(
        "setup",
        help="Auto-detect Obsidian and create a user-wide config",
    )
    p_setup.add_argument(
        "--vault",
        dest="vault_path",
        help="Existing Obsidian vault (auto-detected when omitted)",
    )
    p_setup.add_argument(
        "--config",
        dest="config_path",
        help="Advanced: config destination (defaults to the OS user config)",
    )
    p_setup.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing config that selects a different vault",
    )
    p_setup.add_argument(
        "--pull-models",
        action="store_true",
        help="Download the configured Ollama models required for this vault",
    )
    p_setup.set_defaults(func=cmd_setup)

    p_init = sub.add_parser("init", help="Create kb.toml and vault folders")
    p_init.add_argument("--vault", dest="vault_path", required=True)
    p_init.set_defaults(func=cmd_init)

    p_build = sub.add_parser("build", help="Ingest PDFs / notes into the library")
    p_build.add_argument("inputs", nargs="+", help="Files or directories")
    p_build.add_argument("-r", "--recursive", action="store_true")
    p_build.add_argument(
        "--no-rewrite-source",
        dest="rewrite_source_notes",
        action="store_false",
        default=None,
        help="Do not touch existing .md notes (only generated notes are written)",
    )
    p_build.add_argument(
        "--ingester",
        dest="ingester",
        help="PDF backend: pymupdf4llm (default) | docling | ocr | nougat (math)",
    )
    _add_common(p_build)
    p_build.set_defaults(func=cmd_build)

    p_figures = sub.add_parser(
        "enrich-figures",
        help="Backfill figures into existing generated PDF paper notes",
    )
    p_figures.add_argument(
        "--apply",
        action="store_true",
        help="Actually extract, describe, and write figures (default: dry run)",
    )
    p_figures.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most this many eligible notes",
    )
    p_figures.add_argument(
        "--force",
        action="store_true",
        help="Reprocess notes that already have indexed figures",
    )
    _add_common(p_figures)
    p_figures.set_defaults(func=cmd_enrich_figures)

    p_integrate_figures = sub.add_parser(
        "integrate-figures",
        help="Weave indexed figure evidence into existing generated study notes",
    )
    p_integrate_figures.add_argument(
        "--apply",
        action="store_true",
        help="Actually write inline visual evidence blocks (default: dry run)",
    )
    p_integrate_figures.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most this many eligible notes",
    )
    p_integrate_figures.add_argument(
        "--force",
        action="store_true",
        help="Regenerate managed visual evidence that already exists",
    )
    _add_common(p_integrate_figures)
    p_integrate_figures.set_defaults(func=cmd_integrate_figures)

    p_search = sub.add_parser("search", help="Semantic search over chunks")
    p_search.add_argument("query")
    p_search.add_argument("-k", type=int, dest="k", default=None)
    _add_common(p_search)
    p_search.set_defaults(func=cmd_search)

    p_ask = sub.add_parser("ask", help="RAG answer grounded in your library")
    p_ask.add_argument("query")
    p_ask.add_argument("-k", type=int, dest="k", default=None)
    _add_common(p_ask)
    p_ask.set_defaults(func=cmd_ask)

    p_watch = sub.add_parser(
        "watch", help="Auto-detect new Zotero PDFs and build them"
    )
    p_watch.add_argument(
        "--scan",
        action="store_true",
        help="Process existing un-ingested Zotero PDFs once, then exit",
    )
    p_watch.add_argument("--zotero-dir", dest="zotero_dir", help="Zotero data directory")
    p_watch.add_argument(
        "--interval", type=int, dest="watch_interval", default=None,
        help="Seconds between scans (default 15)",
    )
    _add_common(p_watch)
    p_watch.set_defaults(func=cmd_watch)

    p_relink = sub.add_parser("relink", help="Recompute related-literature links")
    _add_common(p_relink)
    p_relink.set_defaults(func=cmd_relink)

    p_wiki = sub.add_parser(
        "wiki", help="Fill concept notes with wiki-style articles (+ LaTeX math)"
    )
    _add_common(p_wiki)
    p_wiki.set_defaults(func=cmd_wiki)

    p_org = sub.add_parser(
        "organize", help="Auto-organise Knowledge Library folders + MOCs (LLM)"
    )
    p_org.add_argument(
        "--apply",
        action="store_true",
        help="Actually move notes and write MOCs (default: dry run / plan only)",
    )
    p_org.add_argument(
        "--aggressive",
        action="store_true",
        help="Librarian mode: redesign the whole Domain/Subtopic taxonomy",
    )
    _add_common(p_org)
    p_org.set_defaults(func=cmd_organize)

    p_stats = sub.add_parser("stats", help="Show store statistics")
    _add_common(p_stats)
    p_stats.set_defaults(func=cmd_stats)

    p_doctor = sub.add_parser("doctor", help="Check config, store, Zotero, and Ollama")
    p_doctor.add_argument(
        "--skip-ollama",
        action="store_true",
        help="Do not attempt an Ollama server health check",
    )
    _add_common(p_doctor)
    p_doctor.set_defaults(func=cmd_doctor)

    p_refile = sub.add_parser(
        "refile",
        help="File existing paper notes into <references>/<Domain>/<Subdomain>/ folders",
    )
    p_refile.add_argument(
        "--apply",
        action="store_true",
        help="Actually move the notes (default: dry run / plan only)",
    )
    p_refile.add_argument(
        "--plan-out",
        dest="plan_out",
        help="Write a Markdown review plan for planned, skipped, and blocked moves",
    )
    _add_common(p_refile)
    p_refile.set_defaults(func=cmd_refile)

    p_retag = sub.add_parser(
        "retag",
        help="Consolidate paper-note tags into a documented vocabulary (LLM)",
    )
    p_retag.add_argument(
        "--apply",
        action="store_true",
        help="Write the Tag Registry and rewrite note tags (default: dry run)",
    )
    p_retag.add_argument(
        "--concepts",
        action="store_true",
        help="Enrich Knowledge Library concept notes with topical tags "
        "instead of consolidating paper-note tags",
    )
    _add_common(p_retag)
    p_retag.set_defaults(func=cmd_retag)

    p_gc = sub.add_parser(
        "gc", help="Clean the store: orphaned rows, duplicate documents"
    )
    p_gc.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete (default: dry run / report only)",
    )
    _add_common(p_gc)
    p_gc.set_defaults(func=cmd_gc)

    p_fixmath = sub.add_parser(
        "fix-math", help="Strip spaces inside inline math in every generated note"
    )
    _add_common(p_fixmath)
    p_fixmath.set_defaults(func=cmd_fix_math)

    p_inteq = sub.add_parser(
        "integrate-equations",
        help="Weave each note's Key Equations section into its Approach prose (LLM)",
    )
    _add_common(p_inteq)
    p_inteq.set_defaults(func=cmd_integrate_equations)

    return parser


# --------------------------------------------------------------------------- #
#  Config plumbing
# --------------------------------------------------------------------------- #
_OVERRIDE_KEYS = (
    "vault_path",
    "references_dir",
    "llm_model",
    "embed_model",
    "embed_dim",
    "ollama_host",
    "rewrite_source_notes",
    "zotero_dir",
    "watch_interval",
    "ingester",
    "figure_mode",
    "figure_backend",
    "vision_model",
    "figure_assets_dir",
)


def _config_from_args(args: argparse.Namespace) -> Config:
    overrides = {k: getattr(args, k, None) for k in _OVERRIDE_KEYS}
    return load_config(overrides)


def _run_locked(config: Config, owner: str, func) -> int:
    from kb import pipeline

    try:
        with pipeline.PipelineLock(config, owner):
            return func()
    except pipeline.PipelineLockError as exc:
        print(str(exc), file=sys.stderr)
        return 3


# --------------------------------------------------------------------------- #
#  Commands
# --------------------------------------------------------------------------- #
def _choose_setup_vault(args: argparse.Namespace) -> Path:
    if args.vault_path:
        return validate_obsidian_vault(args.vault_path)

    candidates = discover_obsidian_vaults()
    if len(candidates) == 1:
        print(f"Detected Obsidian vault: {candidates[0]}")
        return candidates[0]

    if not sys.stdin.isatty():
        if candidates:
            choices = "\n".join(f"  - {candidate}" for candidate in candidates)
            raise ConfigError(
                "Multiple Obsidian vaults were found in a non-interactive session. "
                "Rerun with --vault PATH. Candidates:\n" + choices
            )
        raise ConfigError(
            "No Obsidian vault was detected. Rerun with --vault PATH."
        )

    if candidates:
        print("Obsidian vaults:")
        for index, candidate in enumerate(candidates, start=1):
            print(f"  {index}. {candidate}")
        answer = input("Choose a vault [1]: ").strip() or "1"
        try:
            selection = int(answer)
            if selection < 1 or selection > len(candidates):
                raise ValueError
            selected = candidates[selection - 1]
        except ValueError as exc:
            raise ConfigError(f"Invalid vault selection: {answer!r}") from exc
        return selected

    answer = input("Path to an existing Obsidian vault: ").strip()
    if not answer:
        raise ConfigError("An Obsidian vault path is required.")
    return validate_obsidian_vault(answer)


def _pull_ollama_models(models: list[str]) -> bool:
    executable = shutil.which("ollama")
    if executable is None:
        print(
            "[FAIL] Ollama CLI was not found. Install it from https://ollama.com "
            "and rerun setup with --pull-models.",
            file=sys.stderr,
        )
        return False

    succeeded = True
    for model in dict.fromkeys(models):
        print(f"Pulling Ollama model: {model}")
        completed = subprocess.run([executable, "pull", model], check=False)
        if completed.returncode:
            print(
                f"[FAIL] ollama pull {model} exited with {completed.returncode}.",
                file=sys.stderr,
            )
            succeeded = False
    return succeeded


def cmd_setup(args: argparse.Namespace) -> int:
    from kb import zotero

    vault = _choose_setup_vault(args)
    default_path = user_config_path()
    cfg_path = (
        Path(args.config_path).expanduser()
        if args.config_path
        else default_path
    )
    try:
        cfg_path = cfg_path.resolve()
    except OSError:
        cfg_path = cfg_path.absolute()

    wrote = write_user_config(vault, cfg_path, force=args.force)
    config = load_config(
        {"vault_path": str(vault)},
        config_path=cfg_path,
    )
    config.ensure_dirs()

    print("\nPaperRoach setup")
    print(f"[OK] Vault       {vault}")
    action = "Wrote" if wrote else "Kept"
    print(f"[OK] Config      {action} {cfg_path}")
    print(f"[OK] References  {config.references_path}")
    print(f"[OK] Store       {config.kb_path}")

    forced_config = os.environ.get("KB_CONFIG")
    local_config = (Path.cwd() / "kb.toml").resolve()
    if (
        not forced_config
        and local_config.is_file()
        and local_config != cfg_path
    ):
        print(
            f"[WARN] {local_config} is checked before the user config while "
            "commands run from this directory."
        )

    if forced_config:
        try:
            forced_path = Path(forced_config).expanduser().resolve()
        except OSError:
            forced_path = Path(forced_config).expanduser().absolute()
        if forced_path != cfg_path:
            print(
                f"[WARN] KB_CONFIG={forced_config} overrides this setup config. "
                "Unset it before running PaperRoach."
            )

    forced_vault = os.environ.get("KB_VAULT")
    if forced_vault:
        try:
            forced_vault_path = Path(forced_vault).expanduser().resolve()
        except OSError:
            forced_vault_path = Path(forced_vault).expanduser().absolute()
        if forced_vault_path != vault:
            print(
                f"[WARN] KB_VAULT={forced_vault} overrides the selected vault. "
                "Unset it before running PaperRoach."
            )

    if cfg_path != default_path.resolve():
        print(
            "[WARN] Custom config path selected. Set KB_CONFIG to this path "
            "before later commands."
        )

    data_dir = zotero.find_data_dir(config)
    if data_dir is None:
        print("[WARN] Zotero      Not detected; set zotero_dir later if needed.")
    else:
        print(f"[OK] Zotero      {data_dir}")

    required_models = [config.llm_model, config.embed_model]
    if config.figure_mode == "describe":
        required_models.append(config.vision_model)
    if args.pull_models and not _pull_ollama_models(required_models):
        return 1
    if not args.pull_models:
        print("[NEXT] Models      Download after Ollama is installed:")
        for model in dict.fromkeys(required_models):
            print(f"  ollama pull {model}")

    print("\nNext:")
    print("  paperroach doctor")
    print('  paperroach build "path/to/one-paper.pdf"')
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    vault = Path(args.vault_path).expanduser()
    vault.mkdir(parents=True, exist_ok=True)

    cfg_path = Path.cwd() / "kb.toml"
    if cfg_path.exists():
        print(f"kb.toml already exists at {cfg_path} (left unchanged).")
    else:
        try:
            template = files("kb").joinpath("templates", "kb.example.toml").read_text(
                encoding="utf-8"
            )
        except FileNotFoundError:
            template = ""
        vault_str = str(vault).replace("\\", "/")
        if template:
            import re

            template = re.sub(
                r'^vault_path\s*=.*$',
                f'vault_path = "{vault_str}"',
                template,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            template = f'vault_path = "{vault_str}"\n'
        cfg_path.write_text(template, encoding="utf-8")
        print(f"Wrote {cfg_path}")
    # Create the folders the *effective* config actually uses (kb.toml may
    # point references_dir/kb_dir somewhere other than the defaults).
    try:
        load_config({"vault_path": str(vault)}).ensure_dirs()
    except ConfigError:
        (vault / "References").mkdir(exist_ok=True)
        (vault / ".kb").mkdir(exist_ok=True)
    print(f"Vault ready at {vault}")
    print("\nNext:")
    print("  ollama pull qwen3:8b")
    print("  ollama pull bge-m3")
    print("  # Optional figure descriptions: ollama pull qwen2.5vl:7b")
    print("  paperroach doctor")
    print('  paperroach build "path/to/paper.pdf"')
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)
    paths = [Path(p) for p in args.inputs]

    def run() -> int:
        result = pipeline.build(paths, config, recursive=args.recursive)
        if result.get("succeeded") or result.get("skipped_duplicates"):
            return 0
        return 1

    return _run_locked(config, "build", run)


def cmd_enrich_figures(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)

    def run() -> int:
        result = pipeline.enrich_figures(
            config, apply=args.apply, limit=args.limit, force=args.force
        )
        return 2 if result.get("needs_mode") else 0

    if args.apply:
        return _run_locked(config, "enrich-figures", run)
    return run()


def cmd_integrate_figures(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)

    def run() -> int:
        pipeline.integrate_figures(
            config, apply=args.apply, limit=args.limit, force=args.force
        )
        return 0

    if args.apply:
        return _run_locked(config, "integrate-figures", run)
    return run()


def cmd_search(args: argparse.Namespace) -> int:
    from kb import rag

    config = _config_from_args(args)
    rows = rag.search(args.query, config, k=args.k)
    print(rag.format_search_results(rows))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from kb import rag

    config = _config_from_args(args)
    result = rag.ask(args.query, config, k=args.k)
    print(result["answer"])
    if result.get("sources"):
        print("\nSources")
        for s in result["sources"]:
            loc = f"  ({s['note_path']})" if s.get("note_path") else ""
            print(f"  • {s['title']}{loc}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)
    result = pipeline.watch(config, scan_only=args.scan)
    return 3 if result.get("locked") else 0


def cmd_relink(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)

    def run() -> int:
        pipeline.relink(config)
        return 0

    return _run_locked(config, "relink", run)


def cmd_wiki(args: argparse.Namespace) -> int:
    from kb import knowledge
    from kb.ollama_client import OllamaClient

    config = _config_from_args(args)

    def run() -> int:
        client = OllamaClient(config)
        print("Filling Knowledge Library concept notes wiki-style (LLM) …")
        n = knowledge.fill_concept_notes(client, config)
        print(f"\nEnriched {n} concept note(s) with wiki-style articles.")
        return 0

    return _run_locked(config, "wiki", run)


def cmd_organize(args: argparse.Namespace) -> int:
    from collections import defaultdict

    from kb import organize

    config = _config_from_args(args)

    def run() -> int:
        if args.aggressive:
            print("Librarian mode — designing a coherent taxonomy (LLM) …")
            moves, notes, tree = organize.plan_aggressive(config)
        else:
            print("Planning Knowledge Library organisation (LLM, conservative) …")
            moves, notes = organize.plan(config)
            tree = None
        if not notes:
            print("No Knowledge Library notes found.")
            return 0

        if tree is not None:
            print(f"\nProposed taxonomy ({len(notes)} notes → {len(tree)} folders):")
            for folder in sorted(tree):
                print(f"  {folder}/  ({len(tree[folder])})")

        print(f"\n{len(moves)} proposed move(s):")
        by_target: dict[str, list] = defaultdict(list)
        for path, current, target in moves:
            by_target[target].append((path.stem, current))
        for target in sorted(by_target):
            print(f"\n  → {target}/")
            for name, current in sorted(by_target[target]):
                print(f"      {name}   (from {current or '(root)'})")

        if not args.apply:
            flag = " --aggressive" if args.aggressive else ""
            print(
                f"\nDry run — nothing changed. Re-run `paperroach organize{flag} --apply` to "
                "move the notes and write per-folder MOC index notes."
            )
            return 0

        backup = organize.backup_library(config)
        print(f"\nBacked up Knowledge Library → {backup}")
        moved = organize.apply_moves(moves, config)
        mocs = organize.write_mocs(config)
        print(f"Applied: moved {moved} note(s); wrote {mocs} MOC index note(s).")
        return 0

    if args.apply:
        return _run_locked(config, "organize", run)
    return run()


def cmd_refile(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)
    plan_out = Path(args.plan_out) if args.plan_out else None

    def run() -> int:
        pipeline.refile_references(config, apply=args.apply, plan_out=plan_out)
        return 0

    if args.apply:
        return _run_locked(config, "refile", run)
    return run()


def cmd_retag(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)

    def run() -> int:
        if args.concepts:
            pipeline.retag_concepts(config, apply=args.apply)
        else:
            pipeline.retag(config, apply=args.apply)
        return 0

    if args.apply:
        return _run_locked(config, "retag", run)
    return run()


def cmd_gc(args: argparse.Namespace) -> int:
    from kb import pipeline
    from kb import store as store_mod

    config = _config_from_args(args)

    def run() -> int:
        pipeline.gc(config, apply=args.apply)
        return 0

    if args.apply and store_mod.table_names(config):
        return _run_locked(config, "gc", run)
    return run()


def cmd_fix_math(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)

    def run() -> int:
        n = pipeline.fix_math_in_all_notes(config)
        print(f"Fixed inline math in {n} note(s).")
        return 0

    return _run_locked(config, "fix-math", run)


def cmd_integrate_equations(args: argparse.Namespace) -> int:
    from kb import pipeline

    config = _config_from_args(args)

    def run() -> int:
        n = pipeline.integrate_all_equations(config)
        print(f"Integrated equations in {n} note(s).")
        return 0

    return _run_locked(config, "integrate-equations", run)


def cmd_stats(args: argparse.Namespace) -> int:
    from kb import store as store_mod

    config = _config_from_args(args)
    n_docs, n_chunks = store_mod.row_counts(config)
    n_figures = store_mod.figure_count(config)
    print(f"Vault       : {config.vault_path}")
    print(f"Store       : {config.kb_path}")
    print(f"Documents   : {n_docs}")
    print(f"Chunks      : {n_chunks}")
    print(f"Figures     : {n_figures} indexed ({config.figure_mode})")
    print(f"LLM model   : {config.llm_model}")
    print(f"Embed model : {config.embed_model} ({config.embed_dim}-dim)")
    print(f"Vision model: {config.vision_model}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from kb import store as store_mod
    from kb import zotero

    config = _config_from_args(args)
    failures = 0
    warnings = 0

    def line(status: str, label: str, detail: str) -> None:
        print(f"[{status}] {label:<12} {detail}")

    def ok(label: str, detail: str) -> None:
        line("OK", label, detail)

    def warn(label: str, detail: str) -> None:
        nonlocal warnings
        warnings += 1
        line("WARN", label, detail)

    def fail(label: str, detail: str) -> None:
        nonlocal failures
        failures += 1
        line("FAIL", label, detail)

    print("PaperRoach doctor")
    ok("Version", __version__)
    ok("Vault", str(config.vault_path))

    if config.references_path.exists():
        ok("References", str(config.references_path))
    else:
        warn("References", f"missing until init/build creates it: {config.references_path}")

    if not config.kb_path.exists():
        warn("Store", f"not initialized yet: {config.kb_path}")
    else:
        try:
            names = store_mod.table_names(config)
            if not names:
                warn("Store", f"no LanceDB tables yet: {config.kb_path}")
            else:
                store = store_mod.KBStore(config)
                n_docs, n_chunks = store.counts()
                ok("Store", f"{n_docs} document(s), {n_chunks} chunk(s)")
        except Exception as exc:
            fail("Store", str(exc))

    if config.figure_mode != "off":
        try:
            if config.figure_backend == "docling":
                import docling  # noqa: F401
            else:
                import pymupdf  # noqa: F401

            ok("Figures", f"{config.figure_mode} via {config.figure_backend}")
        except ModuleNotFoundError:
            dependency = "Docling" if config.figure_backend == "docling" else "PyMuPDF"
            fail("Figures", f"{dependency} missing; install PaperRoach dependencies")

    data_dir = zotero.find_data_dir(config)
    if data_dir is None:
        if config.zotero_dir:
            fail("Zotero", f"configured path is invalid: {config.zotero_dir}")
        else:
            warn("Zotero", "data directory not found; set zotero_dir if needed")
    else:
        pdf_count = len(zotero.storage_pdfs(data_dir))
        ok("Zotero", f"{data_dir} ({pdf_count} PDF attachment(s))")

    if args.skip_ollama:
        warn("Ollama", "skipped")
    else:
        from kb.ollama_client import OllamaClient

        try:
            client = OllamaClient(config)
            client.ping()
            ok("Ollama", config.ollama_host)
            installed = client.installed_models()
            required = [
                ("Text model", config.llm_model),
                ("Embed model", config.embed_model),
            ]
            if config.figure_mode == "describe":
                required.append(("Vision model", config.vision_model))
            for label, model in required:
                aliases = {model}
                if ":" not in model:
                    aliases.add(f"{model}:latest")
                if aliases & installed:
                    ok(label, model)
                else:
                    fail(label, f"{model} is not installed; run: ollama pull {model}")
        except Exception as exc:
            fail("Ollama", str(exc))

    print(f"Summary: {failures} failure(s), {warnings} warning(s)")
    return 1 if failures else 0


# --------------------------------------------------------------------------- #
#  Entrypoint
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    # Windows redirects default to the locale codepage (cp949 on Korean
    # systems), which cannot encode the pipeline's log glyphs (⇄, ·, →) —
    # `paperroach build > log.txt` would crash mid-batch. Force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - top-level friendly error
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
