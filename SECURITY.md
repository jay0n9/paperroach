# Security Policy

## Supported Versions

Security fixes are applied to the latest development branch and the current
`0.1.x` release line while PaperRoach remains pre-1.0.

## Reporting a Vulnerability

Do not publish exploit details, private vault content, PDFs, Zotero databases,
or tokens in a public issue. Use the repository Security tab's **Report a
vulnerability** flow when it is available. If a private reporting channel is
not available, open a minimal public issue requesting private contact without
including technical details.

Include the affected version, environment, reproduction steps, impact, and a
safe proof of concept. Expect an acknowledgement within seven days and a
coordinated disclosure plan for confirmed issues.

## In Scope

- Unsafe writes, deletes, moves, or path traversal affecting a vault.
- Parsing untrusted PDFs or Markdown.
- Prompt injection that can alter local data outside documented behavior.
- Dependency, package-distribution, CI, or local Ollama-host security issues.

Local-first does not mean a threat disappears: a configured remote Ollama host
can receive paper content. Treat host configuration and library data as
sensitive.
