# PaperRoach

[![CI](https://github.com/jay0n9/paperroach/actions/workflows/ci.yml/badge.svg)](https://github.com/jay0n9/paperroach/actions/workflows/ci.yml)

PaperRoach is a local-first paper knowledge pipeline for researchers who keep
papers in Zotero and notes in Obsidian. It turns PDFs and Markdown notes into a
linked Obsidian knowledge library, backed by LanceDB vector search and local
Ollama models.

The project is designed for modest GPUs. The LLM and embedding model are never
kept resident together: PaperRoach extracts and analyzes first, unloads the
LLM, then loads the embedder for indexing and retrieval.

```text
PDF papers / Markdown notes
        |
        v
PASS A0: ingest to Markdown
        |
        v
PASS A1: metadata, analysis, paper-domain classification, concepts
        |
        v
model swap: unload LLM, load embedder
        |
        v
PASS B: chunk embeddings, summary embeddings, LanceDB upsert
        |
        v
Obsidian notes, concept notes, tags, related-paper links
```

## Features

- Ingest PDFs and Markdown notes.
- Auto-detect Zotero storage and process new attachment PDFs.
- Enrich notes from Zotero bibliographic metadata, including venue and DOI,
  when available.
- Generate detailed English paper notes for Obsidian.
- Classify papers into research domains and subdomains, such as
  `Computer Science / Computer Graphics` or `HCI / VR/AR Interaction`.
- Create merge-safe Knowledge Library concept notes.
- Maintain a controlled tag registry with aliases.
- Search and ask questions over the local library using LanceDB and Ollama.
- Keep user-written `## My Notes` sections intact across rebuilds.

## Requirements

- Python 3.11+
- Ollama running locally at `http://localhost:11434`
- Recommended models:

```bash
ollama pull qwen3:8b
ollama pull bge-m3
# Optional, for figure_mode = "describe"
ollama pull qwen2.5vl:7b
```

## Install

```bash
pip install -e .
```

Or install runtime dependencies without installing the package:

```bash
pip install -r requirements.txt
```

The primary CLI is `paperroach`. The older `kb` command remains as a
compatibility alias.

For manual commands and development checks, use Python 3.11 or 3.12 in a
dedicated virtual environment, then install the project with `pip install -e .`.
This is the same supported Python range exercised by CI on Windows and Linux.
Optional PDF backends such as OCR, Docling, and Nougat should be installed only
in that environment.

## Configure

```bash
paperroach init --vault "C:/Users/you/Documents/MyVault"
```

This creates `References/` and `.kb/` in your vault and writes `kb.toml` in the
current directory. See `kb/templates/kb.example.toml` for all options.

Configuration precedence:

```text
CLI flags > KB_* environment variables > kb.toml > built-in defaults
```

If `KB_CONFIG` is set, it must point to an existing TOML file. Invalid TOML,
boolean, and integer values fail fast with field-specific configuration errors.
When `--vault` or `KB_VAULT` selects a different vault than an automatically
discovered `kb.toml`, PaperRoach ignores that mismatched config file so another
vault's absolute `kb_dir` or model settings are not reused by accident. Set
`KB_CONFIG` to force a specific config file.

Generated note prose and RAG answers default to English. You can change this in
`kb.toml` with `note_language` and `answer_language`.

## Build

```bash
paperroach build "C:/papers/attention-is-all-you-need.pdf"
paperroach build "C:/papers" -r
paperroach build paper1.pdf paper2.pdf "C:/notes"
```

For each input, PaperRoach:

1. Extracts Markdown from the source.
2. Optionally extracts figures into vault-visible assets and describes them with
   a local vision model.
3. Extracts metadata and paper analysis with the LLM.
4. Classifies the paper by contribution domain.
5. Distills concepts and drafts concept-note content.
6. Chunks the document.
7. Unloads the LLM and loads the embedding model.
8. Embeds prose chunks, summaries, and figure evidence.
9. Finds related papers from the existing store and writes paper/source notes.
10. Commits successfully written documents to LanceDB and creates concept notes.
11. Saves the content-hash ledger and refreshes related-paper links.

PDFs become generated paper notes under:

```text
<vault>/<references_dir>/<Domain>/<Subdomain>/*.md
```

Markdown notes are indexed for search and related-linking. Existing user notes
are not overwritten; PaperRoach only manages marker-delimited blocks.

`paperroach build` exits with code 0 only when at least one document is
successfully indexed or every remaining input is a known duplicate. If nothing
is processed, automation receives a non-zero exit code.

## Generated Notes

Generated paper notes use YAML frontmatter and a study-note body:

```markdown
---
Date: 2026-06-22
Type:
- Paper
Status: Unread
Authors: Tianye Li et al.
Year: 2017
Domain: Computer Science
Subdomain: Computer Graphics
Secondary Domains:
- HCI
Contribution Type: method
Methods:
- statistical shape modeling
Venue: ACM Transactions on Graphics
Venue Type: journalArticle
DOI: 10.1145/example
Source: https://example.org/paper
tags: [paper, face-model]
kb-generated: true
---
# Learning a model of facial shape and expression from 4D scans

## TL;DR
...

## Problem & Motivation
...

## Approach
...

## Key Results
...

## Contributions
...

## Strengths & Limitations
...

## Concepts
- [[FLAME Model]]

## Related Papers
%% kb-related-start %%
- [[Active Shape Models-Their Training and Application (1995)]]
%% kb-related-end %%

## My Notes
```

## Domain Classification

PaperRoach separates a paper's main contribution domain from incidental tools.
For example, a VR relaxation system evaluated with participants should be filed
as HCI even if it uses generative models or VR rendering. This avoids treating
tool keywords as the research area.

The classifier combines:

- A controlled taxonomy in `kb/taxonomy.py`.
- A controlled subdomain taxonomy for nested filing and frontmatter.
- An LLM classification pass in `kb/llm.py`.
- A heuristic fallback when the LLM is unavailable.
- Frontmatter persistence through `Domain`, `Secondary Domains`,
  `Subdomain`, `Contribution Type`, and `Methods`.

Subdomain filing is metadata-first: explicit `Subdomain` frontmatter or Zotero
`Extra` hints win, then metadata hints such as tags, venue, DOI/source URL, and
title are used before the generated note body is inspected. In Zotero `Extra`,
use lines such as `PaperRoach Domain: HCI` and
`PaperRoach Subdomain: Health & Wellbeing` for explicit control.

## Zotero Watcher

```bash
paperroach watch --scan
paperroach watch
```

The watcher auto-detects the Zotero data directory from the Zotero profile,
including custom `dataDir` values. Override it with:

```bash
paperroach watch --zotero-dir "D:/Zotero"
```

New PDFs under `storage/` are built once, keyed by path and content hash. Failed
builds are retried on later cycles, and a shared `pipeline.lock` heartbeat
prevents the watcher and manual write commands from racing on the same store.

When a PDF is a Zotero attachment, PaperRoach reads bibliographic fields from
`zotero.sqlite` in read-only mode: title, authors, year, tags, URL, venue,
item type, DOI, volume, issue, pages, publisher, and explicit `Domain` /
`Subdomain` hints from Zotero `Extra`.

## Query

```bash
paperroach search "self-attention computational complexity"
paperroach ask "What is the core idea behind attention in these papers?"
```

`search` uses the embedding model only. `ask` embeds the query, unloads the
embedder, then loads the LLM to answer from retrieved context.

## Maintenance

```bash
paperroach doctor
paperroach stats
paperroach relink
paperroach refile
paperroach retag
paperroach organize
paperroach gc
```

Useful maintenance commands:

- `doctor`: check config, vault/store compatibility, Zotero discovery, and
  Ollama reachability. Use `--skip-ollama` for offline checks.
- `stats`: show document and chunk counts.
- `relink`: recompute related-paper and related-concept links.
- `refile`: move generated paper notes into domain/subdomain folders. Add
  `--plan-out refile-plan.md` to write a reviewable Markdown move plan before
  applying changes.
- `retag`: consolidate generated note tags into the Tag Registry.
- `organize`: plan or apply Knowledge Library folder organization.
- `gc`: report or remove orphaned store rows and duplicate generated notes.

Read-only commands such as `stats`, `search`, `ask`, `doctor`, and dry-run
`gc` return empty results or warnings without initializing `.kb` when the store
does not exist yet.

Commands that can move or rewrite files default to dry-run mode unless `--apply`
is provided.

## Development Checks

Pull requests run the same checks on GitHub Actions for Python 3.11 and 3.12
on Linux, macOS, and Windows.

```bash
python -m unittest discover -s tests -v
python -m compileall -q kb paperroach tests
python -m pip wheel . --no-deps -w dist
```

The test suite includes taxonomy regression checks for metadata-first subdomain
filing, pure-function edge cases, and a stubbed `build -> search -> ask` smoke
test that exercises the real local store without requiring a live Ollama server.

Release and versioning steps are documented in `RELEASE.md`.

The vector store writes `.kb/store_meta.json` with the store schema version,
embedding model, and embedding dimension. If you change `embed_model` or
`embed_dim`, rebuild the store instead of reusing incompatible vectors.

## Community

PaperRoach is an early public project and welcomes focused contributions. Read
`CONTRIBUTING.md` for local setup, test expectations, and data-safety rules.
Community standards are in `CODE_OF_CONDUCT.md`; responsible disclosure is in
`SECURITY.md`; maintainer decision-making is described in `GOVERNANCE.md`.

If you use PaperRoach in research, see `CITATION.cff`.

## PDF Parsing

The default PDF backend is `pymupdf4llm` on CPU. Scanned PDFs can fall back to
OCR with `rapidocr-onnxruntime`.

Optional backends:

- `docling` for higher-fidelity scientific parsing.
- `nougat` for math-aware PDF parsing and real LaTeX equation extraction.

Set the backend in `kb.toml`:

```toml
ingester = "pymupdf4llm"
```

Or per command:

```bash
paperroach build "paper.pdf" --ingester nougat
```

## Figure-Aware Parsing

Figure enrichment is opt-in. In `extract` mode PaperRoach saves useful figure
crops and captions; `describe` additionally analyzes each crop with a local
vision model. Assets live under `Assets/PaperRoach/<doc-id>/`, generated paper
notes receive a `## Key Figures` section, and visual evidence is searchable
alongside prose chunks. New paper notes place up to three figure-grounded
findings and inline previews directly inside the relevant `Approach`, `Key
Results`, or other study-note section, so the visual evidence appears where the
reader needs it.

```bash
pip install -e ".[docling]"
ollama pull qwen2.5vl:7b
paperroach build "paper.pdf" --figure-mode describe
# Fully offline embedded-image extraction:
paperroach build "paper.pdf" --figure-mode extract --figure-backend pymupdf
```

To enrich papers that were indexed before figure support existed, use the
backfill command. It reads each generated note's original `kb-source` PDF,
preserves the existing analysis and `## My Notes` content, and updates only the
generated Key Figures section and figure index. Preview first, then apply:

```bash
paperroach enrich-figures --figure-mode describe --figure-backend pymupdf
paperroach enrich-figures --figure-mode describe --figure-backend pymupdf --apply
```

Use `--limit N` to process a smaller batch. Papers with indexed figures are
skipped by default; add `--force` to refresh them. The default command is a dry
run; only `--apply` writes assets, notes, and LanceDB figure rows.

For notes that already have indexed figures, weave that evidence into the
existing study summary without re-ingesting the PDF or rewriting the rest of
the note:

```bash
paperroach integrate-figures
paperroach integrate-figures --apply
```

This creates or refreshes only managed inline visual-evidence blocks, preserves
`## My Notes`, and skips notes already integrated unless `--force` is supplied.
The synthesis uses only indexed figure descriptions and captions; papers whose
visual assets do not support a grounded claim are left unchanged.

When a PDF exposes a figure as many small image tiles rather than one large
embedded crop, the PyMuPDF backend can render the compound page visual as a
fallback. This path runs only when no standalone figure crop qualifies.

```toml
figure_mode = "describe"       # off | extract | describe
figure_backend = "docling"     # docling | pymupdf
vision_model = "qwen2.5vl:7b"
figure_assets_dir = "Assets/PaperRoach"
figure_max_per_paper = 12
figure_min_area_ratio = 0.02
```

`docling` is the preferred layout-aware backend: it can associate pictures,
tables, captions, and page geometry. Its first use may need locally cached
model artifacts. `pymupdf` is a fast offline fallback for PDFs that contain
embedded raster images; it cannot reliably recover vector-only diagrams or
complex table structure. Figure descriptions are supporting evidence for paper
analysis and HCI classification, never a source for bibliographic metadata.

PaperRoach loads the vision model, then unloads it before the text LLM and
embedder run, so the three models do not co-reside on an 8 GB GPU. Figure crops
remain in the local vault; do not commit PDFs or extracted assets from
copyrighted papers to the project repository.

## Project Layout

```text
kb/
  cli.py             command-line interface
  templates/          packaged `paperroach init` configuration template
  pipeline.py        build, watch, relink, refile, retag, gc
  ingest.py          PDF / Markdown ingestion
  figures.py         figure crops, vision evidence, and vault assets
  llm.py             LLM prompts and JSON coercion
  taxonomy.py        paper-domain taxonomy and heuristic fallback
  obsidian.py        generated notes and managed blocks
  knowledge.py       concept notes and Knowledge Library operations
  store.py           LanceDB tables and vector search
  rag.py             search and grounded question answering
paperroach/
  __main__.py        package alias for `python -m paperroach`
scripts/
  smoke_wheel.py      isolated wheel-install smoke test
```

## License

MIT. See `LICENSE`.
