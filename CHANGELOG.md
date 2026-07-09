# Changelog

All notable user-facing changes should be recorded here before a tagged
release. Follow semantic versioning and keep entries short enough to scan.

## Unreleased

### Added

- `paperroach doctor` for config, store, Zotero, and Ollama health checks.
- Store metadata validation for schema version, embedding model, and embedding
  dimension compatibility.
- Release checklist and changelog template.

### Changed

- Documented vector store compatibility and future migration expectations.

### Fixed

- _None yet._

### Migration Notes

- Existing stores without `.kb/store_meta.json` will write metadata the next
  time PaperRoach opens them successfully. Changing `embed_model` or
  `embed_dim` after that requires rebuilding or migrating the store.

## 0.1.0

### Added

- Initial public PaperRoach package with local-first paper ingestion, Obsidian
  note generation, Zotero metadata enrichment, LanceDB search, and Ollama-based
  analysis.
