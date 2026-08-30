# Markdown viewer third-party notices

The public case-study Markdown viewer vendors these browser distributions so the
viewer does not depend on a runtime CDN:

- markdown-it 15.0.1 — MIT License — `LICENSE.markdown-it`
- DOMPurify 3.4.14 — Apache License 2.0 / MPL 2.0 dual license — distributed
  here under Apache License 2.0 in `LICENSE.dompurify`
- KaTeX 0.18.4 — MIT License — `katex/LICENSE.katex`

These libraries are viewer infrastructure. They do not alter the published PDF
or Markdown artifacts, whose hashes remain recorded in `../manifest.json` and
`../SHA256SUMS.txt`.
