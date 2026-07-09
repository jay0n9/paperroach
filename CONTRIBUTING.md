# Contributing to PaperRoach

Thanks for helping make PaperRoach useful beyond a single vault and machine.
The project accepts bug fixes, documentation improvements, ingestion backends,
taxonomy improvements, tests, and carefully scoped product changes.

## Before You Start

1. Search existing issues and pull requests.
2. For a large feature or a behavior change, open an issue first and describe
   the user problem, proposed interface, migration impact, and test plan.
3. Do not include private PDFs, Zotero databases, vault notes, API tokens, or
   personal paths in an issue, test fixture, commit, or pull request.

## Development Setup

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows PowerShell
pip install -e .
python -m unittest discover -s tests -v
```

On macOS or Linux, activate with `source .venv/bin/activate`. Core tests use
stubbed Ollama clients and do not need a running Ollama server. Manual PDF,
OCR, Docling, and Nougat checks should use disposable vaults and public or
synthetic input files only.

## Change Guidelines

- Keep a pull request focused on one user-visible concern.
- Preserve user-authored note content and use managed markers for generated
  blocks. File moves and deletes must have a dry-run or explicit confirmation.
- Add regression coverage for every bug fix.
- Prefer deterministic pure functions for taxonomy, parsing, and path logic.
- Treat `kb/templates/kb.example.toml`, README, and data-pipeline documentation
  as part of the public product contract when configuration or data changes.
- Document rebuild or migration requirements when changing note schemas,
  LanceDB schemas, embedding compatibility, or document identities.

## Required Checks

Run these before opening a pull request:

```bash
python -m unittest discover -s tests -v
python -m compileall -q kb paperroach tests
python -m pip wheel . --no-deps -w dist
python scripts/smoke_wheel.py dist
```

The wheel smoke test installs the built artifact in a clean virtual environment
and verifies that `paperroach init` writes a usable configuration template.

## Architecture Map

- `kb/ingest.py`: PDF and Markdown ingestion backends.
- `kb/llm.py`: structured extraction, analysis, and classification prompts.
- `kb/pipeline.py`: build, watch, maintenance, and write coordination.
- `kb/store.py`: LanceDB schemas, compatibility checks, and vector operations.
- `kb/obsidian.py`, `kb/knowledge.py`: note rendering and managed updates.
- `kb/taxonomy.py`: controlled paper domain and subdomain vocabulary.

Read `DATA_PIPELINE.md` before changing a data boundary. Changes that add an
ingester, embedder, classifier, or exporter should keep the existing local-first
and limited-VRAM behavior intact.

## Pull Requests

Use a descriptive title, explain the observable behavior change, and include
tests. Keep generated build artifacts, `.kb` stores, local configuration,
Zotero data, and PDFs out of commits. Maintainers may request a smaller scope
or an issue-backed design discussion before merging a broad change.
