# Changelog

All notable user-facing changes should be recorded here before a tagged
release. Follow semantic versioning and keep entries short enough to scan.

## Unreleased

### Added

- `paperroach doctor` for config, store, Zotero, and Ollama health checks.
- Store metadata validation for schema version, embedding model, and embedding
  dimension compatibility.
- Release checklist and changelog template.
- Contributor, governance, code-of-conduct, security, citation, CODEOWNERS,
  issue-form, pull-request, and Dependabot foundations for public development.
- Isolated wheel-install smoke testing in CI.
- Optional figure-aware PDF enrichment with Docling-first extraction, an
  offline PyMuPDF fallback, local vision descriptions, Obsidian figure embeds,
  and LanceDB figure retrieval.
- `paperroach enrich-figures` to backfill visual evidence into existing
  generated paper notes without rerunning full paper analysis.

### Changed

- Metadata extraction now preserves explicit `Domain` and `Subdomain` fields
  before classifier or body-text fallback cues are considered.
- Documented vector store compatibility and future migration expectations.
- `paperroach init` now loads its configuration template from packaged data, so
  installed wheels generate the full documented configuration file.
- Long-running write locks now heartbeat automatically; the Zotero watcher
  only holds a writer lock while it is actually building a batch.
- Configuration now rejects invalid pipeline sizes, unsafe vault-relative
  output paths, and unknown PDF ingesters before work starts.
- Figure extraction is opt-in and uses a separate vision-model pass so visual,
  text, and embedding models do not co-reside on an 8 GB GPU.

### Fixed

- Automatically discovered `kb.toml` files for a different vault are ignored
  when `--vault` or `KB_VAULT` selects another vault, preventing accidental
  reuse of another vault's absolute store path or model settings.
- Read-only commands now avoid initializing `.kb` on fresh vaults when the
  store does not exist yet.
- `paperroach stats` now validates existing store metadata compatibility
  without creating or rewriting store files.
- Generated and managed Markdown updates now use atomic replacement writes.
- `gc --apply` now deletes only generated PDF duplicates whose current source
  bytes match exactly; same-title/year papers remain review-only candidates.
- Content-hash ledger updates now retire stale hashes when a source file changes.

### Migration Notes

- Existing stores without `.kb/store_meta.json` will write metadata the next
  time PaperRoach opens them successfully. Changing `embed_model` or
  `embed_dim` after that requires rebuilding or migrating the store.

## 0.1.0

### Added

- Initial public PaperRoach package with local-first paper ingestion, Obsidian
  note generation, Zotero metadata enrichment, LanceDB search, and Ollama-based
  analysis.
