# PaperRoach Release Checklist

PaperRoach does not publish automatically yet. Use this checklist for tagged
builds so the package metadata, CLI version, and GitHub tag stay aligned.

## Versioning

Use semantic versions:

- Patch: bug fixes, test hardening, documentation-only release notes.
- Minor: new commands, new metadata fields, new ingestion/search behavior.
- Major: incompatible config, note schema, database, or CLI behavior changes.

Update both version sources in the same commit:

- `pyproject.toml` -> `[project].version`
- `kb/__init__.py` -> `__version__`
- `CHANGELOG.md` -> move user-facing changes from `Unreleased` into the release

The test suite checks that these two values match.

## Pre-Release Checks

Run the same checks as CI:

```bash
python -m unittest discover -s tests -v
python -m compileall -q kb paperroach tests
python -m pip wheel . --no-deps -w dist
python scripts/smoke_wheel.py dist
python -m paperroach --version
```

For a release that changes ingestion, Zotero enrichment, note rendering, or the
LanceDB store, also run one manual build against a disposable vault. For a
figure-aware release, use a PDF with an embedded image and verify the vault
asset, `## Key Figures` note section, and figure search result.

If the release changes LanceDB table schemas, generated frontmatter fields, or
embedding compatibility, document whether users must rebuild `<vault>/.kb` or
can run an in-place migration.

## Tagging

Create the version commit first, then tag that exact commit:

```bash
git status --short
git add pyproject.toml kb/__init__.py CHANGELOG.md RELEASE.md
git commit -m "Release 0.1.1"
git tag -a v0.1.1 -m "PaperRoach 0.1.1"
git push origin main
git push origin v0.1.1
```

After pushing, confirm GitHub Actions passes for the tag/commit before sharing
the release publicly.

## Artifacts

Build artifacts are local and ignored by Git:

```bash
python -m pip wheel . --no-deps -w dist
```

Attach the wheel from `dist/` to a GitHub Release if distributing a binary
artifact. Do not commit `dist/`, local vaults, Zotero data, PDFs, logs, or
machine-specific watcher scripts.
