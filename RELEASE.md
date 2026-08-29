# PaperRoach Release Checklist

Publishing a GitHub Release triggers `.github/workflows/publish-to-pypi.yml`.
That workflow builds one source distribution and one wheel, verifies them,
passes the exact artifacts to a separate publishing job, and authenticates to
PyPI with OpenID Connect (OIDC). It does not use a PyPI API token or any other
repository secret.

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

If setup, supported Python versions, optional dependencies, or model defaults
change, repeat the applicable path in `INSTALL.md` and update the guide in the
same release.

## One-Time Trusted Publisher Setup

Complete this before publishing the first GitHub Release:

1. In the GitHub repository settings, create an environment named `pypi`.
   Environment approval rules are optional but recommended for a production
   package index.
2. In PyPI's publishing settings, add a trusted publisher (or a pending trusted
   publisher if the `paperroach` project does not exist yet) with these exact
   values:
   - PyPI project: `paperroach`
   - GitHub owner: `jay0n9`
   - GitHub repository: `paperroach`
   - Workflow filename: `publish-to-pypi.yml`
   - Environment: `pypi`
3. Do not create a `PYPI_API_TOKEN` secret. The publishing job receives a
   short-lived token only after GitHub and PyPI verify the workflow identity.

The trusted-publisher fields are identity constraints. Renaming the repository,
workflow file, or GitHub environment requires updating the PyPI publisher
configuration before the next release.

## Tagging and Publishing

Create the version commit first, merge it to `main`, and wait for CI to pass.
Then tag that exact commit:

```bash
git status --short
git add pyproject.toml kb/__init__.py CHANGELOG.md RELEASE.md
git commit -m "Release 0.1.1"
git tag -a v0.1.1 -m "PaperRoach 0.1.1"
git push origin main
git push origin v0.1.1
```

Create a **draft** GitHub Release for the tag and review its title, notes, and
target. A draft does not publish to PyPI. Publish the GitHub Release only after:

- the tag is exactly `v` followed by `[project].version` from `pyproject.toml`;
- CI has passed for the tagged commit;
- the changelog and install guide are current; and
- the PyPI trusted publisher configuration above is active.

Publishing the GitHub Release starts the `Publish to PyPI` workflow. There is no
manual workflow trigger, which prevents an arbitrary branch or commit from
being selected for publication. The build job checks out the release tag and
refuses to continue when the tag and package version differ.

## Artifacts

The workflow builds the sdist and wheel once in its unprivileged `build` job. It
runs strict metadata checks, validates archive paths, smoke-tests the wheel, and
uploads both files as a short-lived GitHub Actions artifact. The `publish` job
only downloads those verified files and uploads them to PyPI. OIDC's
`id-token: write` permission exists only on that publishing job.

For a local pre-release inspection, build artifacts remain ignored by Git:

```bash
python -m pip install build twine
python -m build --sdist --wheel --outdir dist
python -m twine check --strict dist/*
```

Do not commit `dist/`, local vaults, Zotero data, PDFs, logs, or
machine-specific watcher scripts. PyPI versions and files are immutable: if a
published build is wrong, fix it and release a new version instead of trying to
replace an existing file.

After publication, verify both jobs succeeded and confirm the release at
<https://pypi.org/project/paperroach/>. If trusted authentication fails, compare
the owner, repository, workflow filename, and environment on PyPI with the
values above before rerunning the failed job.
