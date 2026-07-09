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

## Configure

```bash
paperroach init --vault "C:/Users/you/Documents/MyVault"
```

This creates `References/` and `.kb/` in your vault and writes `kb.toml` in the
current directory. See `kb.example.toml` for all options.

Configuration precedence:

```text
CLI flags > KB_* environment variables > kb.toml > built-in defaults
```

If `KB_CONFIG` is set, it must point to an existing TOML file. Invalid TOML,
boolean, and integer values fail fast with field-specific configuration errors.

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
2. Extracts metadata and paper analysis with the LLM.
3. Classifies the paper by contribution domain.
4. Distills concepts and drafts concept-note content.
5. Chunks the document.
6. Unloads the LLM and loads the embedding model.
7. Stores chunk and summary embeddings in LanceDB.
8. Finds related papers and writes Obsidian notes.
9. Creates or merges concept notes in the Knowledge Library.

PDFs become generated paper notes under:

```text
<vault>/<references_dir>/<Domain>/<Subdomain>/*.md
```

Markdown notes are indexed for search and related-linking. Existing user notes
are not overwritten; PaperRoach only manages marker-delimited blocks.

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

Subdomain filing is metadata-first: explicit `Subdomain` frontmatter wins, then
metadata hints such as tags, venue, DOI/source URL, and title are used before
the generated note body is inspected.

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
builds are retried on later cycles, and a `watch.lock` heartbeat prevents two
watchers from racing on the same store.

When a PDF is a Zotero attachment, PaperRoach reads bibliographic fields from
`zotero.sqlite` in read-only mode: title, authors, year, tags, URL, venue,
item type, DOI, volume, issue, pages, and publisher.

## Query

```bash
paperroach search "self-attention computational complexity"
paperroach ask "What is the core idea behind attention in these papers?"
```

`search` uses the embedding model only. `ask` embeds the query, unloads the
embedder, then loads the LLM to answer from retrieved context.

## Maintenance

```bash
paperroach stats
paperroach relink
paperroach refile
paperroach retag
paperroach organize
paperroach gc
```

Useful maintenance commands:

- `stats`: show document and chunk counts.
- `relink`: recompute related-paper and related-concept links.
- `refile`: move generated paper notes into domain/subdomain folders. Add
  `--plan-out refile-plan.md` to write a reviewable Markdown move plan before
  applying changes.
- `retag`: consolidate generated note tags into the Tag Registry.
- `organize`: plan or apply Knowledge Library folder organization.
- `gc`: report or remove orphaned store rows and duplicate generated notes.

Commands that can move or rewrite files default to dry-run mode unless `--apply`
is provided.

## Development Checks

Pull requests run the same checks on GitHub Actions for Python 3.11 and 3.12
on Linux and Windows.

```bash
python -m unittest discover -s tests -v
python -m compileall -q kb paperroach tests
python -m pip wheel . --no-deps -w dist
```

The test suite includes taxonomy regression checks for metadata-first subdomain
filing, including hyphenated tags such as `computer-graphics`,
`computer-vision`, and `deep-learning`.

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

## Project Layout

```text
kb/
  cli.py             command-line interface
  pipeline.py        build, watch, relink, refile, retag, gc
  ingest.py          PDF / Markdown ingestion
  llm.py             LLM prompts and JSON coercion
  taxonomy.py        paper-domain taxonomy and heuristic fallback
  obsidian.py        generated notes and managed blocks
  knowledge.py       concept notes and Knowledge Library operations
  store.py           LanceDB tables and vector search
  rag.py             search and grounded question answering
paperroach/
  __main__.py        package alias for `python -m paperroach`
```

## License

MIT. See `LICENSE`.
