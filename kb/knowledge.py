"""Knowledge Library concept notes (stage ⑦b).

For each concept surfaced in a paper's analysis, create a distilled note under
``<vault>/6 - Knowledge Library/<Subject>/<Concept>.md`` matching the vault's
"Concept" convention, and link it back to the source paper.

Merge-safe: a concept note that already exists ANYWHERE in the Knowledge
Library (user-made or from another paper) is never overwritten — only a
``- From: [[paper]]`` backlink is appended to its ``## Source`` section. This
keeps the same concept shared across papers and protects hand-written notes.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import re
from pathlib import Path

import yaml

from kb import tags as tags_mod
from kb.config import Config
from kb.llm import write_concept_article
from kb.models import Document
from kb.obsidian import (
    _read_text_tolerant,
    fix_inline_math,
    is_generated_note,
    safe_note_name,
    split_frontmatter,
    wikilink,
)

_SOURCE_HEADING = "## Source"
_RC_START = "%% kb-related-concepts-start %%"
_RC_END = "%% kb-related-concepts-end %%"
_RC_HEADING = "## Related Concepts"


def list_subjects(config: Config) -> list[str]:
    """Existing Knowledge Library subfolder names (domains)."""
    kl = config.knowledge_library_path
    if not kl.exists():
        return []
    return sorted(
        p.name for p in kl.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def write_concept_notes(doc: Document, config: Config) -> list[Path]:
    """Create/merge concept notes for ``doc``. Returns the note paths touched."""
    if not config.create_concept_notes:
        return []
    an = doc.analysis
    if not an or not an.concepts or not doc.link_target:
        return []

    subject = _safe_subject(an.subject, config)
    folder = config.knowledge_library_path / subject
    # Fold the LLM's per-concept tags onto the shared Tag Registry vocabulary
    # (same controlled vocabulary the paper notes use), registering new ones.
    registry = tags_mod.load_registry(config)
    for c in an.concepts:
        c["tags"] = tags_mod.canonicalize(c.get("tags") or [], registry, limit=5)
    tags_mod.register_new(
        config, registry, [t for c in an.concepts for t in c.get("tags") or []]
    )
    # One directory walk for the whole paper, not one per concept.
    index = _library_index(config)
    touched: list[Path] = []
    for concept in an.concepts:
        name = (concept.get("name") or "").strip()
        if not name or not (concept.get("explanation") or "").strip():
            continue  # skip concepts the LLM didn't elaborate
        try:
            path = _write_one(
                name, concept, subject, folder, doc.link_target, config, index
            )
            if path is not None:
                touched.append(path)
        except OSError as exc:
            print(f"      ! could not write concept note '{name}': {exc}", flush=True)
            continue
    return touched


def _write_one(
    name: str,
    concept: dict,
    subject: str,
    folder: Path,
    paper_link: str,
    config: Config,
    index: dict[str, Path],
) -> Path | None:
    existing = index.get(_safe_name(name).lower())
    if existing is not None and existing.exists():
        _append_source_link(existing, paper_link)
        if is_generated_note(existing):
            _set_parent_if_missing(existing, (concept.get("parent") or "").strip())
        return existing
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_safe_name(name)}.md"
    path.write_text(
        fix_inline_math(_render_concept(name, concept, subject, paper_link)),
        encoding="utf-8",
    )
    index[path.stem.lower()] = path
    return path


def _concept_tags(subject: str, concept: dict) -> list[str]:
    """Subject tag (vault's underscore convention) + the concept's topic tags."""
    tags = [subject.replace(" ", "_")] if subject else []
    seen = {tags_mod._squash(t) for t in tags}
    for t in concept.get("tags") or []:
        key = tags_mod._squash(t)
        if t and key not in seen:
            tags.append(t)
            seen.add(key)
    return tags[: tags_mod.MAX_TAGS_PER_NOTE]


def _library_index(config: Config) -> dict[str, Path]:
    """{lowercased stem: path} for every note in the Knowledge Library."""
    kl = config.knowledge_library_path
    if not kl.exists():
        return {}
    return {p.stem.lower(): p for p in kl.rglob("*.md") if p.is_file()}


def _render_concept(name: str, concept: dict, subject: str, paper_link: str) -> str:
    parent = (concept.get("parent") or "").strip()
    frontmatter = {
        "Date": _dt.date.today(),
        "Type": ["Concept"],
        "Subject": subject,
        "Parent": [wikilink(parent)] if parent else [],
        "Status": None,
        "tags": _concept_tags(subject, concept),
        "kb-generated": True,
    }
    fm = yaml.safe_dump(
        frontmatter, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).rstrip()
    fm = fm.replace("Status: null", "Status:")  # match the vault's bare convention
    out = ["---", fm, "---", f"# {name}", "---", ""]
    article = (concept.get("article") or "").strip()
    if article:
        out += [article, ""]
    else:
        out += [concept.get("explanation", "").strip(), ""]
        why = (concept.get("why_it_matters") or "").strip()
        if why:
            out += ["## Why it matters", "", why, ""]
    out += [_SOURCE_HEADING, "", f"- From: [[{paper_link}]]", ""]
    out += ["---", "# References", ""]
    return "\n".join(out).rstrip() + "\n"


def _set_parent_if_missing(path: Path, parent: str) -> bool:
    """Add a ``Parent`` frontmatter property (after Subject) if absent.

    Only touches kb-generated concept notes; preserves the body verbatim.
    """
    text = _read_text_tolerant(path)
    fm_text, body = split_frontmatter(text)
    if fm_text is None:
        return False
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return False
    if not isinstance(fm, dict) or fm.get("Parent"):
        return False  # already has a non-empty parent

    value = [wikilink(parent)] if parent else []
    new_fm: dict = {}
    placed = False
    for k, v in fm.items():
        if k == "Parent":
            continue
        new_fm[k] = v
        if k == "Subject":
            new_fm["Parent"] = value
            placed = True
    if not placed:
        new_fm["Parent"] = value

    dumped = yaml.safe_dump(
        new_fm, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).rstrip()
    dumped = dumped.replace("Status: null", "Status:")
    new_text = f"---\n{dumped}\n---\n{body}"
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def fill_concept_notes(client, config: Config) -> int:
    """Rewrite each kb-generated concept note's body as a wiki-style article
    (definition / formulation with LaTeX math / intuition / applications),
    preserving frontmatter, Related Concepts, Source and References."""
    kl = config.knowledge_library_path
    if not kl.exists():
        return 0
    notes = [
        p
        for p in kl.rglob("*.md")
        if p.is_file() and is_generated_note(p) and not p.stem.endswith(" MOC")
    ]
    filled = 0
    for i, p in enumerate(notes, 1):
        context = _note_body(p)
        print(f"  [{i}/{len(notes)}] {p.stem}", flush=True)
        try:
            article = write_concept_article(client, p.stem, context, config)
        except Exception as exc:
            print(f"      ! failed: {exc}", flush=True)
            continue
        if not article.strip():
            continue
        original = _read_text_tolerant(p)
        new = fix_inline_math(_replace_body(original, article))
        if new != original:
            p.write_text(new, encoding="utf-8")
            filled += 1
    return filled


def _replace_body(text: str, new_body: str) -> str:
    """Swap a concept note's prose body, keeping frontmatter + title and the
    trailing managed sections (Related Concepts / Source / References)."""
    fm_text, rest = split_frontmatter(text)
    fm = f"---\n{fm_text}\n---\n" if fm_text is not None else ""
    cut = len(rest)
    for anchor in ("\n## Related Concepts", "\n## Source", "\n# References"):
        i = rest.find(anchor)
        if i != -1:
            cut = min(cut, i)
    head, tail = rest[:cut], rest[cut:]
    m = re.match(r"(\s*#\s+[^\n]+\n---\n)", head)
    title_block = m.group(1) if m else "\n"
    return f"{fm}{title_block}\n{new_body.strip()}\n{tail}"


def _sources_from_text(text: str) -> list[str]:
    """Wikilinks listed under the concept note's ``## Source`` section."""
    m = re.search(r"(?m)^## Source\s*$(.*?)(?:\n#|\Z)", text, re.DOTALL)
    if not m:
        return []
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", m.group(1))


def _ensure_list_props(
    path: Path, additions: list, overwrite: bool = False, text: str | None = None
) -> bool:
    """Insert/refresh list-valued frontmatter properties, preserving the body.

    ``additions`` is ``[(key, values, anchor_key)]``; each property is inserted
    right after ``anchor_key`` (or appended). With ``overwrite=False`` an
    existing non-empty property is left as-is. Pass ``text`` when the caller
    already read the file (avoids a second read).
    """
    if text is None:
        text = _read_text_tolerant(path)
    fm_text, body = split_frontmatter(text)
    if fm_text is None:
        return False
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return False
    if not isinstance(fm, dict):
        return False

    items = list(fm.items())
    changed = False
    for key, values, anchor in additions:
        existing = fm.get(key)
        if existing and not overwrite:
            continue
        if overwrite and existing == values:
            continue
        items = [(k, v) for k, v in items if k != key]
        rebuilt, inserted = [], False
        for k, v in items:
            rebuilt.append((k, v))
            if not inserted and k == anchor:
                rebuilt.append((key, values))
                inserted = True
        if not inserted:
            rebuilt.append((key, values))
        items = rebuilt
        fm[key] = values
        changed = True

    if not changed:
        return False
    dumped = yaml.safe_dump(
        dict(items), allow_unicode=True, sort_keys=False, default_flow_style=False
    ).rstrip()
    dumped = dumped.replace("Status: null", "Status:")
    new_text = f"---\n{dumped}\n---\n{body}"
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def link_siblings(config: Config) -> int:
    """Set each kb concept note's ``Sibling`` property to the other concepts
    that share one of its source papers. Deterministic — no LLM/embeddings."""
    kl = config.knowledge_library_path
    if not kl.exists():
        return 0
    kb_notes = [p for p in kl.rglob("*.md") if p.is_file() and is_generated_note(p)]
    # One read per note; every helper below works on this text.
    texts: dict[Path, str] = {p: _read_text_tolerant(p) for p in kb_notes}
    paper_to_notes: dict[str, list[Path]] = {}
    note_sources: dict[Path, list[str]] = {}
    for p in kb_notes:
        srcs = _sources_from_text(texts[p])
        note_sources[p] = srcs
        for s in srcs:
            paper_to_notes.setdefault(s, []).append(p)

    linked = 0
    for p in kb_notes:
        parents = {n.lower() for n in _links_from_text(texts[p], "Parent")}
        siblings: set[str] = set()
        for s in note_sources[p]:
            for q in paper_to_notes.get(s, []):
                if q.stem.lower() != p.stem.lower() and q.stem.lower() not in parents:
                    siblings.add(q.stem)
        values = [f"[[{n}]]" for n in sorted(siblings)]
        if _ensure_list_props(
            p, [("Sibling", values, "Parent")], overwrite=True, text=texts[p]
        ):
            linked += 1
    return linked


def _links_from_text(text: str, key: str) -> set[str]:
    """Wikilink targets in a list-valued frontmatter property."""
    fm_text, _body = split_frontmatter(text)
    if fm_text is None:
        return set()
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return set()
    val = fm.get(key)
    if not val:
        return set()
    if isinstance(val, str):
        val = [val]
    out: set[str] = set()
    for v in val:
        out.update(re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", str(v)))
    return out


_SOURCE_HEADING_RE = re.compile(r"(?m)^## Source[ \t]*$")


def _append_source_link(path: Path, paper_link: str) -> bool:
    """Add a `- From: [[paper]]` backlink if missing. Never overwrites.

    Uses a line-anchored heading match: a plain substring test would treat a
    hand-written '## Sources' heading as '## Source' and corrupt it.
    """
    text = _read_text_tolerant(path)
    if f"[[{paper_link}]]" in text:
        return False  # already linked — idempotent
    bullet = f"- From: [[{paper_link}]]"
    m = _SOURCE_HEADING_RE.search(text)
    if m:
        updated = text[: m.end()] + f"\n{bullet}" + text[m.end():]
    else:
        updated = text.rstrip() + f"\n\n{_SOURCE_HEADING}\n{bullet}\n"
    path.write_text(updated, encoding="utf-8")
    return True


# --------------------------------------------------------------------------- #
#  Concept-to-concept cross-linking (semantic, library-wide)
# --------------------------------------------------------------------------- #
def concept_id_for(config: Config, path: Path) -> str:
    try:
        rel = path.resolve().relative_to(config.vault_path.resolve())
    except ValueError:
        rel = path
    return hashlib.sha1(str(rel).lower().encode("utf-8")).hexdigest()[:12]


def _note_body(path: Path) -> str:
    """Concept text used for embedding (frontmatter + managed blocks removed)."""
    _fm, text = split_frontmatter(_read_text_tolerant(path))
    text = re.sub(
        re.escape(_RC_START) + r".*?" + re.escape(_RC_END), "", text, flags=re.DOTALL
    )
    return text.strip()[:2000]


def process_concepts(touched_paths, client, store, config: Config) -> int:
    """Index Knowledge Library concept notes and write ``## Related Concepts``
    blocks into the kb-generated ones. ``touched_paths`` limits which notes get
    a block (None → every kb-generated concept note, used by `relink`)."""
    kl = config.knowledge_library_path
    if not kl.exists():
        return 0
    # MOC index files are link lists — embedding them makes them "related" to
    # everything, so they'd crowd real concepts out of every block.
    all_paths = [
        p for p in kl.rglob("*.md") if p.is_file() and not p.stem.endswith(" MOC")
    ]
    if not all_paths:
        return 0

    # Prune ghost rows: notes deleted by hand or moved by `paperroach organize`
    # (concept_id is path-derived) would otherwise haunt Related Concepts
    # forever, recommending dead links and duplicate names.
    for row in store.all_concepts():
        note_path = row.get("note_path") or ""
        if note_path and not Path(note_path).exists():
            store.delete_concept(row["concept_id"])

    indexed = store.indexed_concept_ids()
    touched_ids = {concept_id_for(config, p) for p in (touched_paths or [])}
    to_embed = [
        p
        for p in all_paths
        if concept_id_for(config, p) not in indexed
        or concept_id_for(config, p) in touched_ids
    ]
    for batch in _batches(to_embed, 48):
        vectors = client.embed([f"{p.stem}\n{_note_body(p)}" for p in batch])
        for p, vec in zip(batch, vectors):
            store.upsert_concept(
                {
                    "concept_id": concept_id_for(config, p),
                    "name": p.stem,
                    "note_path": str(p),
                    "subject": p.parent.name,
                    "vector": vec,
                }
            )

    vmap = {r["concept_id"]: list(r["vector"]) for r in store.all_concepts()}
    targets = touched_paths if touched_paths else all_paths
    linked = 0
    for p in targets:
        if not is_generated_note(p):
            continue  # never inject a block into a hand-written note
        cid = concept_id_for(config, p)
        vec = vmap.get(cid)
        if not vec:
            continue
        rows = store.related_concepts(vec, cid, config.related_top_k)
        names = [
            r["name"]
            for r in rows
            if r.get("name") and r["name"].lower() != p.stem.lower()
        ]
        if _write_related_concepts(p, names):
            linked += 1
    return linked


def _batches(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _write_related_concepts(path: Path, names: list[str]) -> bool:
    text = _read_text_tolerant(path)
    body = "\n".join(f"- [[{n}]]" for n in names) if names else "_No related concepts yet_"
    block = f"{_RC_START}\n{body}\n{_RC_END}"
    has_start = _RC_START in text
    has_end = _RC_END in text
    if has_start and has_end:
        updated = re.sub(
            re.escape(_RC_START) + r".*?" + re.escape(_RC_END),
            lambda _m: block,
            text,
            count=1,
            flags=re.DOTALL,
        )
    elif has_start or has_end:
        # One marker was deleted; appending would duplicate the block forever.
        print(
            f"  ! related-concepts block in '{path.name}' has a mismatched "
            f"marker; skipping update.",
            flush=True,
        )
        return False
    else:
        m = _SOURCE_HEADING_RE.search(text)
        if m:
            # Place Related Concepts just before the Source section.
            updated = (
                text[: m.start()]
                + f"{_RC_HEADING}\n\n{block}\n\n"
                + text[m.start():]
            )
        else:
            updated = text.rstrip() + f"\n\n{_RC_HEADING}\n\n{block}\n"
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def _safe_subject(subject: str, config: Config) -> str:
    subject = (subject or "").strip()
    if not subject:
        return "General"
    existing = {s.lower(): s for s in list_subjects(config)}
    if subject.lower() in existing:  # reuse the existing folder casing
        return existing[subject.lower()]
    return _safe_folder(subject)


def _safe_name(name: str) -> str:
    # Shared sanitiser (Windows-invalid chars, brackets, reserved device
    # names) so filenames always agree with the wikilinks pointing at them.
    return safe_note_name(name)


def _safe_folder(name: str) -> str:
    return _safe_name(name) or "General"
