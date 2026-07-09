"""Stage ⑦ — write Obsidian notes (YAML frontmatter + body) and manage the
auto-generated "Related Papers" wikilink block.

Generated reference notes (from PDFs) are rewritten in full each run. Existing
User source notes are never clobbered — only an idempotent marker-delimited
block is inserted / refreshed inside them.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

import yaml

from kb.config import Config
from kb.models import Document, PaperAnalysis

RELATED_START = "%% kb-related-start %%"
RELATED_END = "%% kb-related-end %%"
RELATED_HEADING = "## Related Papers"

_INVALID_FS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WS = re.compile(r"\s+")

# Windows reserved device names can't be used as file basenames.
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Obsidian/MathJax renders inline math ONLY as `$x$` — a space just inside the
# delimiters (`$ x $`) suppresses rendering. Match single-$ spans (never $$…$$).
_INLINE_MATH = re.compile(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)")

_MATH_CHARS = set("\\^_={}")


def fix_inline_math(text: str) -> str:
    """Strip whitespace just inside single-$ inline math (`$ x $` -> `$x$`).
    Leaves display math ($$...$$) and everything else untouched. Spans that
    look like prose currency ("costs $100 to $200") are left alone."""

    def _fix(m: re.Match) -> str:
        content = m.group(1)
        # "$100 to $" — starts with a digit and contains no math syntax:
        # almost certainly two dollar amounts in prose, not an equation.
        if content[:1].isdigit() and not (_MATH_CHARS & set(content)):
            return m.group(0)
        return f"${content.strip()}$"

    return _INLINE_MATH.sub(_fix, text)


# --------------------------------------------------------------------------- #
#  Filenames / link targets
# --------------------------------------------------------------------------- #
def sanitize_filename(title: str, year: int | None) -> str:
    base = safe_note_name(title)
    if year:
        base = f"{base} ({year})"
    return base


def safe_note_name(name: str) -> str:
    """A Windows-safe, wikilink-safe note basename for ``name``.

    ``[``/``]`` are legal in filenames but corrupt ``[[...]]`` wikilinks, so
    they are replaced too. Reserved device names (CON, AUX, …) silently fail
    as file basenames on Windows.
    """
    base = _INVALID_FS.sub(" ", str(name))
    base = base.replace("[", "(").replace("]", ")")
    base = _WS.sub(" ", base).strip().strip(".")
    base = base[:120].strip() or "Untitled"
    if base.upper() in _RESERVED_NAMES:
        base = f"{base} (concept)"
    return base


def wikilink(name: str) -> str:
    """Render ``[[...]]`` for a concept name, aliasing when the note filename
    had to be sanitised — so the link always resolves to the actual file."""
    safe = safe_note_name(name)
    if safe == name:
        return f"[[{safe}]]"
    alias = str(name).replace("|", "/").replace("[", "(").replace("]", ")").strip()
    if alias == safe:
        return f"[[{safe}]]"
    return f"[[{safe}|{alias}]]"


def assign_note_location(doc: Document, config: Config) -> None:
    """Set ``doc.note_path`` and ``doc.link_target`` deterministically.

    Must run *before* storage so related-linking can reference link targets
    regardless of processing order. With ``references_by_subject`` the note is
    filed under ``<references_dir>/<Subject>/`` (wikilinks resolve by basename,
    so the folder is free to vary).
    """
    if doc.kind == "note":
        # Index the user's own note in place; link by its basename.
        doc.note_path = doc.source_path
        doc.link_target = doc.source_path.stem
        return
    name = sanitize_filename(doc.metadata.title, doc.metadata.year)
    name = _dedupe_against(name, config.references_path, doc.source_path)
    doc.link_target = name
    subject = ""
    subdomain = ""
    if doc.classification and doc.classification.primary_domain:
        subject = doc.classification.primary_domain.strip()
        subdomain = doc.classification.subdomain.strip()
    elif doc.metadata.primary_domain:
        subject = doc.metadata.primary_domain.strip()
        subdomain = doc.metadata.subdomain.strip()
    elif doc.analysis:
        subject = (doc.analysis.subject or "").strip()
    folder = reference_classification_folder(config, subject, subdomain)
    doc.note_path = folder / f"{name}.md"


def reference_classification_folder(
    config: Config, domain: str, subdomain: str = ""
) -> Path:
    """The folder a paper note belongs in: <references>/<Domain>/<Subdomain>."""
    folder = reference_subject_folder(config, domain)
    if (
        not config.references_by_subject
        or not config.references_by_subdomain
        or not subdomain.strip()
    ):
        return folder
    safe = safe_note_name(subdomain)
    if folder.exists():
        for d in folder.iterdir():
            if d.is_dir() and d.name.lower() == safe.lower():
                return d
    return folder / safe


def reference_subject_folder(config: Config, subject: str) -> Path:
    """The folder a paper note belongs in, reusing an existing subfolder's
    casing when one matches case-insensitively."""
    if not config.references_by_subject or not subject.strip():
        return config.references_path
    safe = safe_note_name(subject)
    if config.references_path.exists():
        for d in config.references_path.iterdir():
            if d.is_dir() and d.name.lower() == safe.lower():
                return d
    return config.references_path / safe


def _dedupe_against(name: str, refs_root: Path, source_path: Path) -> str:
    """Avoid colliding with an *unrelated* existing note of the same title.

    The scan is recursive: wikilinks resolve by basename across the whole
    vault, so a name must be unique across every subject subfolder too.
    """

    def taken(candidate: str) -> bool:
        if not refs_root.exists():
            return False
        for existing in refs_root.rglob(f"{candidate}.md"):
            if not _is_our_note_for(existing, source_path):
                return True
        return False

    if not taken(name):
        return name
    i = 2
    while taken(f"{name} ({i})"):
        i += 1
    return f"{name} ({i})"


def _is_our_note_for(path: Path, source_path: Path) -> bool:
    fm = _read_frontmatter(path)
    return (
        _frontmatter_flag(fm.get("kb-generated"))
        and fm.get("kb-source") == str(source_path)
    )


# --------------------------------------------------------------------------- #
#  Rendering
# --------------------------------------------------------------------------- #
def render_note(doc: Document, related_links: list[str], config: Config) -> str:
    """Render a note matching the vault's "Source Material" frontmatter
    convention (Date / Type / Status / Authors / Year / Source / tags), plus
    hidden kb-* keys used for idempotency."""
    meta = doc.metadata
    # Preserve the original Date across re-runs; only stamp it on first write.
    # A date object dumps unquoted (2026-06-20), matching the vault convention.
    date = _existing_date(doc.note_path) or _dt.date.today()
    source = meta.source_url or (_doi_url(meta.doi) if meta.doi else str(doc.source_path))
    frontmatter = {
        "Date": date,
        "Type": ["Paper"],
        "Status": "Unread",
        "Authors": _format_authors(meta.authors),
        "Year": meta.year,
        "Source": source,
        "tags": _vault_tags(meta.tags),
        "kb-generated": True,
        "kb-source": str(doc.source_path),
        "kb-doc-id": doc.doc_id,
    }
    if meta.venue:
        frontmatter["Venue"] = meta.venue
    if meta.venue_type:
        frontmatter["Venue Type"] = meta.venue_type
    if meta.doi:
        frontmatter["DOI"] = meta.doi
    if meta.volume:
        frontmatter["Volume"] = meta.volume
    if meta.issue:
        frontmatter["Issue"] = meta.issue
    if meta.pages:
        frontmatter["Pages"] = meta.pages
    if meta.publisher:
        frontmatter["Publisher"] = meta.publisher
    cls = doc.classification
    primary_domain = (
        cls.primary_domain if cls and cls.primary_domain else meta.primary_domain
    )
    subdomain = cls.subdomain if cls and cls.subdomain else meta.subdomain
    if primary_domain:
        frontmatter["Domain"] = primary_domain
        if subdomain:
            frontmatter["Subdomain"] = subdomain
        if cls and cls.secondary_domains:
            frontmatter["Secondary Domains"] = cls.secondary_domains
        if cls and cls.contribution_type:
            frontmatter["Contribution Type"] = cls.contribution_type
        if cls and cls.methods:
            frontmatter["Methods"] = cls.methods
    an = doc.analysis or PaperAnalysis()
    out = ["---", _dump_yaml(frontmatter).rstrip(), "---", f"# {meta.title}", "---", ""]

    # Metadata callout (full author list + link).
    out.append("> [!info] Metadata")
    if meta.authors:
        out.append(f"> - **Authors:** {', '.join(meta.authors)}")
    if meta.year:
        out.append(f"> - **Year:** {meta.year}")
    if meta.venue:
        out.append(f"> - **Venue:** {meta.venue}")
    if meta.doi:
        out.append(f"> - **DOI:** {meta.doi}")
    out.append(f"> - **Link:** {source}")
    out.append("")

    if an.tl_dr:
        out += ["## TL;DR", "", an.tl_dr, ""]
    if an.problem_motivation:
        out += ["## Problem & Motivation", "", an.problem_motivation, ""]
    if an.approach:
        out += ["## Approach", "", an.approach, ""]
    if an.key_results:
        out += ["## Key Results", "", an.key_results, ""]
    if an.contributions:
        out += ["## Contributions", ""] + [f"- {c}" for c in an.contributions] + [""]
    if an.strengths or an.limitations:
        out += ["## Strengths & Limitations", ""]
        if an.strengths:
            out.append(f"- **Strengths:** {_join_clauses(an.strengths)}")
        if an.limitations:
            out.append(
                f"- **Limitations & open questions:** {_join_clauses(an.limitations)}"
            )
        out.append("")
    if an.takeaways:
        out += ["## Takeaways", "", an.takeaways, ""]
    if doc.equations and not doc.equations_integrated:
        # Only dump a separate section if the equations weren't woven into the
        # Approach prose above.
        out += ["## Key Equations", "", "_Extracted verbatim from the source._", ""]
        for eq in doc.equations:
            out += [f"$$\n{eq}\n$$", ""]
    if an.concepts:
        out += ["## Concepts", ""]
        out += [f"- {wikilink(c['name'])}" for c in an.concepts if c.get("name")]
        out += ["", "## Concept Map", "", _concept_map(meta.title, an.concepts), ""]

    out += [RELATED_HEADING, "", _related_block(related_links), ""]
    # Re-runs must not clobber what the user wrote under "## My Notes".
    my_notes = _existing_my_notes(doc.note_path)
    out += ["## My Notes", ""]
    if my_notes:
        # The blank line before '---' matters: "text\n---" is a setext heading.
        out += [my_notes, ""]
    else:
        out += [""]
    out += ["---", "# References", "", f"- {_citation(meta)}"]
    if meta.source_url:
        out.append(f"- {meta.source_url}")

    return fix_inline_math("\n".join(out).rstrip() + "\n")


def _join_clauses(items: list[str]) -> str:
    """Semicolon-join clauses, dropping each item's trailing period."""
    return "; ".join(s.strip().rstrip(".").strip() for s in items if s.strip())


def _short(text: str, n: int) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > 0 else cut).rstrip() + "…"


def _concept_map(title: str, concepts: list[dict]) -> str:
    handle = _mm_clean(_short(title.split(":")[0].strip(), 36)) or "Paper"
    lines = ["```mermaid", "graph TD", f'    P["{handle}"]']
    named = [c for c in concepts if c.get("name")]
    for i, c in enumerate(named, 1):
        lines.append(f'    C{i}["{_mm_clean(c["name"])}"]')
    for i, c in enumerate(named, 1):
        rel = _mm_clean(c.get("relation") or "relates to")
        lines.append(f"    P -->|{rel}| C{i}")
    lines.append("```")
    return "\n".join(lines)


def _mm_clean(text: str) -> str:
    """Sanitise text for a mermaid label/edge."""
    return (
        str(text)
        .replace('"', "'")
        .replace("|", "/")
        .replace("[", "(")
        .replace("]", ")")
        .replace("\n", " ")
        .strip()
    )


def _citation(meta) -> str:
    author = _format_authors(meta.authors) or "Unknown"
    year = meta.year if meta.year else "n.d."
    venue = f", {meta.venue}" if meta.venue else ""
    doi = f" doi:{meta.doi}" if meta.doi else ""
    return f'{author}, "{meta.title}", {year}{venue}.{doi}'


def _doi_url(doi: str) -> str:
    doi = str(doi or "").strip()
    if not doi:
        return ""
    if doi.lower().startswith("http"):
        return doi
    return f"https://doi.org/{doi}"


def _format_authors(authors: list[str]) -> str:
    """Vault convention stores Authors as a string ("First Author et al.")."""
    authors = [a for a in (authors or []) if a]
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    return f"{authors[0]} et al."


def _vault_tags(tags: list[str]) -> list[str]:
    """Always lead with 'paper' (vault convention), then topic tags."""
    out = ["paper"]
    for t in tags or []:
        if t and t.lower() != "paper":
            out.append(t)
    return out


def _existing_date(note_path: Path | None):
    """Return the existing note's Date (date object or str), or None."""
    if note_path and note_path.exists():
        return _read_frontmatter(note_path).get("Date") or None
    return None


_MY_NOTES_RE = re.compile(
    r"(?ms)^## My Notes[ \t]*\r?\n(.*?)(?=^---[ \t]*\r?\n# References[ \t]*$|^# References[ \t]*$|\Z)"
)


def _existing_my_notes(note_path: Path | None) -> str:
    """The user-authored body under '## My Notes' in an existing note, if any."""
    if not note_path or not note_path.exists():
        return ""
    m = _MY_NOTES_RE.search(_read_text_tolerant(note_path))
    return m.group(1).strip() if m else ""


def extract_my_notes(path: Path) -> str:
    """Public variant used when migrating a renamed note's user content."""
    return _existing_my_notes(path)


def inject_my_notes(path: Path, content: str) -> bool:
    """Fill an *empty* '## My Notes' section with ``content`` (used when a
    renamed note's user text is migrated). Never overwrites existing text."""
    if not content.strip():
        return False
    text = _read_text_tolerant(path)
    m = _MY_NOTES_RE.search(text)
    if not m or m.group(1).strip():
        return False
    updated = text[: m.start(1)] + content.rstrip() + "\n\n" + text[m.end(1):]
    path.write_text(updated, encoding="utf-8")
    return True


def _related_block(related_links: list[str]) -> str:
    if related_links:
        body = "\n".join(f"- [[{t}]]" for t in related_links)
    else:
        body = "_No related papers._"
    return f"{RELATED_START}\n{body}\n{RELATED_END}"


def write_generated_note(doc: Document, related_links: list[str], config: Config) -> Path:
    assert doc.note_path is not None
    content = render_note(doc, related_links, config)
    doc.note_path.parent.mkdir(parents=True, exist_ok=True)
    doc.note_path.write_text(content, encoding="utf-8")
    return doc.note_path


def update_related_in_file(path: Path, related_links: list[str]) -> bool:
    """Insert / refresh the related block inside an existing file.

    Returns True if the file changed. Never removes user content.
    """
    if not path.exists():
        return False
    original = _read_text_tolerant(path)
    block = _related_block(related_links)

    start_count = original.count(RELATED_START)
    end_count = original.count(RELATED_END)
    if start_count == 1 and end_count == 1:
        pattern = re.escape(RELATED_START) + r".*?" + re.escape(RELATED_END)
        updated, replacements = re.subn(
            pattern,
            lambda _m: block,
            original,
            count=1,
            flags=re.DOTALL,
        )
        if replacements != 1:
            print(
                f"  ! related-links block in '{path.name}' has markers out of "
                "order; skipping update.",
                flush=True,
            )
            return False
    elif start_count or end_count:
        # A marker was hand-edited or duplicated. Appending or partially
        # updating would leave stale managed links in the graph.
        print(
            f"  ! related-links block in '{path.name}' has {start_count} "
            f"start marker(s) and {end_count} end marker(s); skipping update.",
            flush=True,
        )
        return False
    else:
        sep = "" if original.endswith("\n") else "\n"
        updated = f"{original}{sep}\n{RELATED_HEADING}\n\n{block}\n"

    if updated != original:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


# --------------------------------------------------------------------------- #
#  YAML helpers
# --------------------------------------------------------------------------- #
def _dump_yaml(data: dict) -> str:
    return yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    )


def _read_text_tolerant(path: Path) -> str:
    """Read text tolerating a UTF-8 BOM and legacy cp949 notes.

    ``utf-8-sig`` decodes both BOM and BOM-less UTF-8 (and strips the BOM), so
    it must come before the cp949 fallback. Generated notes are always written
    as plain UTF-8, so no BOM is ever re-emitted.
    """
    for enc in ("utf-8-sig", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


# Delimiters are '---' on their OWN line; a value may itself contain '---'
# (e.g. a tag like 'computer-science---computer-vision'), so match the
# line-anchored closing delimiter instead of a naive split('---').
_FRONTMATTER_RE = re.compile(r"---\r?\n(.*?)\r?\n---\s*?(?:\r?\n|$)", re.DOTALL)

_FM_PROBE_BYTES = 16384  # frontmatter is small; avoid full reads of big notes


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split ``text`` into (frontmatter_text, body).

    Shared by every module that edits notes in place — the naive
    ``split('---')`` it replaces breaks on values that contain '---'.
    ``frontmatter_text`` is None when the note has no frontmatter.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def _read_frontmatter(path: Path) -> dict:
    # Probe only the head of the file: this runs over every candidate note
    # during directory scans, and vault notes can be large.
    try:
        with open(path, "rb") as fh:
            raw = fh.read(_FM_PROBE_BYTES)
    except OSError:
        return {}
    text = _decode_tolerant(raw)
    m = _FRONTMATTER_RE.match(text)
    if not m and len(raw) == _FM_PROBE_BYTES:
        # Frontmatter longer than the probe (rare) — fall back to a full read.
        try:
            text = _read_text_tolerant(path)
        except OSError:
            return {}
        m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _decode_tolerant(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def is_generated_note(path: Path) -> bool:
    """True if ``path`` is a note this pipeline produced (skip on re-ingest)."""
    return _frontmatter_flag(_read_frontmatter(path).get("kb-generated"))


def _frontmatter_flag(value) -> bool:
    """Parse a YAML frontmatter flag conservatively."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False
