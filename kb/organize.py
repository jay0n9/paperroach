"""Self-organising Knowledge Library folders.

`kb organize` reviews every note in the Knowledge Library, asks the LLM for the
best domain folder for each (conservatively — keep the current folder unless
clearly wrong), and:

* **dry-run (default)** — prints the proposed moves and per-folder MOC plan,
  changing nothing.
* **--apply** — moves notes into ``<Knowledge Library>/<Domain>/`` (Obsidian
  wikilinks resolve by basename, so links survive the move) and writes a Map of
  Content (MOC) index note in each folder.
"""
from __future__ import annotations

import datetime as _dt
import re
import shutil
from pathlib import Path

from kb.config import Config
from kb.knowledge import _batches, _safe_folder, list_subjects
from kb.obsidian import _read_text_tolerant, is_generated_note, split_frontmatter
from kb.ollama_client import OllamaClient

MOC_SUFFIX = " MOC"
# Leading emoji sorts before letters/digits in Obsidian's file explorer, so
# every MOC pins to the top of its folder. Detection stays suffix-based
# (_is_moc), so pre-emoji MOC files are still recognised (and migrated).
MOC_PREFIX = "🗺️ "
_MOC_START = "%% kb-moc-start %%"
_MOC_END = "%% kb-moc-end %%"

_ORGANIZE_SYSTEM = (
    "You are organising a personal knowledge vault into domain folders. For each "
    "note you get its current folder, title, and a snippet. Assign the single "
    "best domain folder. STRONGLY PREFER keeping the current folder — only "
    "reassign when the current folder is clearly wrong for the note's topic. "
    "Choose a domain from this list when one fits: {domains}. If none fits, "
    "propose a concise Title Case domain. Return ONLY JSON: "
    '{"assignments": [{"name": "<exact title>", "domain": "<folder>"}]}.'
)


def _gather_notes(config: Config) -> list[dict]:
    kl = config.knowledge_library_path
    notes = []
    for p in kl.rglob("*.md"):
        if not p.is_file() or _is_moc(p):
            continue
        rel = p.relative_to(kl).parts
        if any(part.startswith(".") for part in rel):
            continue
        domain = rel[0] if len(rel) > 1 else "(root)"
        rel_dir = str(p.parent.relative_to(kl)).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        notes.append(
            {
                "path": p,
                "name": p.stem,
                "domain": domain,
                "rel_dir": rel_dir,
                "snippet": _snippet(p),
            }
        )
    return notes


def _snippet(path: Path, limit: int = 240) -> str:
    _fm, text = split_frontmatter(_read_text_tolerant(path))
    text = " ".join(text.split())
    return text[:limit]


def _classify(client: OllamaClient, notes: list[dict], domains: list[str]) -> dict:
    system = _ORGANIZE_SYSTEM.replace("{domains}", ", ".join(domains))
    listing = "\n".join(
        f"- name: {n['name']}\n  current_folder: {n['domain']}\n  snippet: {n['snippet']}"
        for n in notes
    )
    obj = client.generate_json(system, f"Notes:\n{listing}\n\nReturn the JSON now.")
    out = {}
    for a in obj.get("assignments", []) or []:
        if isinstance(a, dict) and a.get("name"):
            out[str(a["name"]).strip()] = str(a.get("domain") or "").strip()
    return out


def plan(config: Config) -> tuple[list[tuple], list[dict]]:
    """Return (moves, all_notes). moves = [(path, current_domain, target_domain)]."""
    notes = _gather_notes(config)
    if not notes:
        return [], []
    domains = sorted({n["domain"] for n in notes if n["domain"] != "(root)"}
                     | set(list_subjects(config)))
    client = OllamaClient(config)
    assignments: dict[str, str] = {}
    for batch in _batches(notes, 12):
        assignments.update(_classify(client, batch, domains))

    ambiguous = _duplicate_names(notes)
    moves = []
    for n in notes:
        if n["name"] in ambiguous:
            continue  # two notes share this stem; an LLM answer keyed by name
            # can't tell them apart, so leave both where they are
        target = assignments.get(n["name"], "")
        target = _safe_folder(target) if target else n["domain"]
        if target and target != n["domain"] and target != "(root)":
            moves.append((n["path"], n["domain"], target))
    return moves, notes


def _duplicate_names(notes: list[dict]) -> set[str]:
    seen: set[str] = set()
    dups: set[str] = set()
    for n in notes:
        if n["name"] in seen:
            dups.add(n["name"])
        seen.add(n["name"])
    if dups:
        print(
            f"  ! {len(dups)} note name(s) exist in multiple folders and will "
            f"not be moved: {', '.join(sorted(dups))}",
            flush=True,
        )
    return dups


_CLUSTER_SYSTEM = (
    "You are the librarian. All notes below belong to the '{domain}' domain but "
    "sit at its root with no subtopic. CLUSTER them into a SMALL number of "
    "coherent subtopics — put closely related notes in the SAME subtopic and "
    "avoid one-note subtopics unless a note is truly standalone. Use clear, "
    "correctly-spelled Title Case subtopic names. Reuse these existing subtopics "
    "when they genuinely fit: {subtopics}. Return ONLY JSON: "
    '{"assignments": [{"name": "<title>", "subtopic": "<Subtopic>"}]}.'
)


def _cluster_subtopics(
    client: OllamaClient, domain: str, notes: list[dict], existing: list[str]
) -> dict:
    system = _CLUSTER_SYSTEM.replace("{domain}", domain).replace(
        "{subtopics}", ", ".join(existing) or "(none)"
    )
    listing = "\n".join(f"- name: {n['name']}\n  snippet: {n['snippet']}" for n in notes)
    obj = client.generate_json(system, f"Notes:\n{listing}\n\nReturn the JSON now.")
    out = {}
    for a in obj.get("assignments", []) or []:
        if isinstance(a, dict) and a.get("name") and a.get("subtopic"):
            out[str(a["name"]).strip()] = _safe_folder(str(a["subtopic"]))
    return out


def plan_aggressive(config: Config) -> tuple[list[tuple], list[dict], dict]:
    """Refined librarian mode: PRESERVE notes already filed in a subtopic, and
    cluster the notes scattered at a domain root into coherent subtopics WITHIN
    their current domain (domain is fixed — only the subtopic is chosen).

    Returns (moves, notes, tree) where tree maps target folder -> [names]."""
    notes = _gather_notes(config)
    if not notes:
        return [], [], {}

    # rel_dir == "Domain" (single component) => scattered at a domain root.
    deep = [n for n in notes if "/" in n["rel_dir"]]
    shallow = [n for n in notes if n["rel_dir"] and "/" not in n["rel_dir"]]

    subs_by_domain: dict[str, set] = {}
    for n in deep:
        dom, sub = n["rel_dir"].split("/", 1)
        subs_by_domain.setdefault(dom, set()).add(sub.split("/")[0])

    by_domain: dict[str, list] = {}
    for n in shallow:
        by_domain.setdefault(n["domain"], []).append(n)

    client = OllamaClient(config)
    assign: dict[str, str] = {}  # name -> subtopic
    for domain, dnotes in by_domain.items():
        existing = sorted(subs_by_domain.get(domain, set()))
        try:
            assign.update(_cluster_subtopics(client, domain, dnotes, existing))
        except Exception:
            continue

    ambiguous = _duplicate_names(notes)
    moves, tree = [], {}
    for n in deep:  # preserved in place
        tree.setdefault(n["rel_dir"], []).append(n["name"])
    for n in shallow:
        sub = assign.get(n["name"]) if n["name"] not in ambiguous else None
        target = f"{n['domain']}/{sub}" if sub else n["rel_dir"]
        tree.setdefault(target, []).append(n["name"])
        if target != n["rel_dir"]:
            moves.append((n["path"], n["rel_dir"], target))
    return moves, notes, tree


_BACKUP_KEEP = 5


def backup_library(config: Config) -> Path:
    """Copy the whole Knowledge Library to a backup before any reorganisation.

    Backups live under ``<kb_path>/backups``: ``kb_path`` is either a
    dot-folder inside the vault (which Obsidian does not index) or a
    user-chosen path outside it — either way the copy never pollutes the
    vault's graph/search with duplicate-basename notes. Only the newest
    ``_BACKUP_KEEP`` backups are retained.
    """
    kl = config.knowledge_library_path
    base = config.kb_path / "backups"
    base.mkdir(parents=True, exist_ok=True)
    stamp = _dt.date.today().isoformat()
    backup = base / f"{kl.name} backup {stamp}"
    n = 2
    while backup.exists():
        backup = base / f"{kl.name} backup {stamp} ({n})"
        n += 1
    shutil.copytree(kl, backup)

    # Retention: drop the oldest backups beyond the keep limit.
    all_backups = sorted(
        (p for p in base.iterdir() if p.is_dir() and p.name.startswith(f"{kl.name} backup")),
        key=lambda p: p.stat().st_mtime,
    )
    for old in all_backups[:-_BACKUP_KEEP]:
        shutil.rmtree(old, ignore_errors=True)
    return backup


def apply_moves(moves: list[tuple], config: Config) -> int:
    kl = config.knowledge_library_path
    moved = 0
    for path, _current, target in moves:
        if not path.exists():
            continue
        dest_dir = kl / target
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / path.name
        if dest.resolve() == path.resolve():
            continue
        if dest.exists():
            # Don't clobber an existing note of the same name — but say so,
            # or the printed plan and the actual result silently disagree.
            print(f"  ! not moved (name already exists at target): {path.name}", flush=True)
            continue
        shutil.move(str(path), str(dest))
        if is_generated_note(dest):
            _update_subject(dest, target.split("/")[0])
        moved += 1
    if moved:
        _prune_empty_dirs(config.knowledge_library_path)
    return moved


def _prune_empty_dirs(kl: Path) -> None:
    """Remove folders left with no real notes (deepest first); drop stale MOCs."""
    dirs = sorted(
        (p for p in kl.rglob("*") if p.is_dir()),
        key=lambda x: len(x.parts),
        reverse=True,
    )
    for d in dirs:
        if any(part.startswith(".") for part in d.relative_to(kl).parts):
            continue
        if any(not _is_moc(p) for p in d.rglob("*.md")):
            continue  # still has real notes
        for moc in list(d.rglob("*.md")):
            # Only delete MOCs this pipeline generated — a user's own
            # "<Something> MOC.md" is their note, not our index.
            if _is_moc(moc) and is_generated_note(moc):
                moc.unlink()
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


def write_mocs(config: Config) -> int:
    """Write a MOC for every note-bearing folder (recursively). A parent folder's
    MOC links to its sub-folder MOCs and lists any notes directly inside it."""
    kl = config.knowledge_library_path
    written = 0
    for folder in _walk_folders(kl):
        direct = sorted(p.stem for p in folder.glob("*.md") if not _is_moc(p))
        subs = sorted(
            d.name
            for d in folder.iterdir()
            if d.is_dir() and not d.name.startswith(".") and _has_notes(d)
        )
        if not direct and not subs:
            continue
        if _write_moc(folder, direct, subs):
            written += 1
    return written


def _walk_folders(kl: Path):
    yield kl
    for p in sorted(kl.rglob("*")):
        if p.is_dir() and not any(part.startswith(".") for part in p.relative_to(kl).parts):
            yield p


def _has_notes(folder: Path) -> bool:
    for p in folder.rglob("*.md"):
        if _is_moc(p):
            continue
        if any(part.startswith(".") for part in p.relative_to(folder).parts):
            continue
        return True
    return False


# --------------------------------------------------------------------------- #
#  MOC + frontmatter helpers
# --------------------------------------------------------------------------- #
def _is_moc(path: Path) -> bool:
    return path.stem.endswith(MOC_SUFFIX)


def _write_moc(folder: Path, note_names: list[str], sub_mocs: list[str]) -> bool:
    moc_path = folder / f"{MOC_PREFIX}{folder.name}{MOC_SUFFIX}.md"
    legacy = folder / f"{folder.name}{MOC_SUFFIX}.md"
    if legacy.exists() and not moc_path.exists() and is_generated_note(legacy):
        legacy.rename(moc_path)
    sections = []
    if sub_mocs:
        sections.append(
            "### Sub-topics\n"
            + "\n".join(f"- [[{MOC_PREFIX}{s}{MOC_SUFFIX}]]" for s in sub_mocs)
        )
    if note_names:
        sections.append(
            "### Notes\n" + "\n".join(f"- [[{n}]]" for n in note_names)
        )
    block = f"{_MOC_START}\n" + "\n\n".join(sections) + f"\n{_MOC_END}"

    if moc_path.exists():
        text = _read_text_tolerant(moc_path)
        if _MOC_START in text and _MOC_END in text:
            new = re.sub(
                re.escape(_MOC_START) + r".*?" + re.escape(_MOC_END),
                lambda _m: block,
                text,
                count=1,
                flags=re.DOTALL,
            )
        else:
            new = text.rstrip() + f"\n\n{block}\n"
        if new == text:
            return False
    else:
        fm = (
            "---\nType:\n- MOC\nSubject: "
            + folder.name
            + "\ntags:\n- MOC\nkb-generated: true\n---\n"
        )
        new = f"{fm}# {folder.name}\n---\n\n{block}\n"
    moc_path.write_text(new, encoding="utf-8")
    return True


def _update_subject(path: Path, subject: str) -> None:
    text = _read_text_tolerant(path)
    fm_text, body = split_frontmatter(text)
    if fm_text is None:
        return
    new_fm = re.sub(
        r"^Subject:.*$", f"Subject: {subject}", fm_text, count=1, flags=re.MULTILINE
    )
    if new_fm != fm_text:
        path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")
