"""Controlled tag vocabulary (the "Tag Registry").

Tags used to be invented freely by the LLM per paper, which produced 100+
mostly-singleton tags with near-duplicate spellings (``computervision`` /
``computer-vision`` / ``DeapLearning`` …). This module keeps one canonical
vocabulary, documented *in the vault* where the user can read and edit it:

    <vault>/<tags_dir>/Tag Registry.md

The registry is a Markdown table between kb markers::

    | tag | description | aliases |
    |---|---|---|
    | computer-vision | Image and video understanding | computervision, cv |

* ``load_registry`` parses it; ``save_registry`` rewrites it (kb-managed).
* ``canonicalize`` maps a tag list onto the vocabulary — alias hits and
  spelling variants (case / hyphen / underscore) collapse to the canonical
  form; unknown tags pass through normalised.
* At build time the canonical tags are offered to the LLM ("prefer these"),
  and genuinely new tags are appended to the registry so the vocabulary and
  its documentation never drift apart.
"""
from __future__ import annotations

import re
from pathlib import Path

from kb.config import Config
from kb.obsidian import _read_text_tolerant, write_text_atomic

REGISTRY_START = "%% kb-tags-start %%"
REGISTRY_END = "%% kb-tags-end %%"
REGISTRY_NAME = "Tag Registry.md"

_ROW_RE = re.compile(r"^\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")

MAX_TAGS_PER_NOTE = 8


def registry_path(config: Config) -> Path:
    return config.vault_path / config.tags_dir / REGISTRY_NAME


def load_registry(config: Config) -> dict[str, dict]:
    """{canonical_tag: {"description": str, "aliases": [str]}} (insertion-ordered)."""
    path = registry_path(config)
    if not path.exists():
        return {}
    text = _read_text_tolerant(path)
    if text.count(REGISTRY_START) != 1 or text.count(REGISTRY_END) != 1:
        return {}
    start = text.find(REGISTRY_START)
    end = text.find(REGISTRY_END)
    if end <= start:
        return {}
    registry: dict[str, dict] = {}
    for line in text[start:end].splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        tag = normalize(m.group(1))
        if not tag or tag in {"tag", "---", ":---"} or set(tag) <= {"-", ":"}:
            continue  # header / separator rows
        aliases = [normalize(a) for a in m.group(3).split(",")]
        registry[tag] = {
            "description": m.group(2).strip(),
            "aliases": [a for a in aliases if a and a != tag],
        }
    return registry


def save_registry(config: Config, registry: dict[str, dict]) -> Path:
    """Write the registry note (kb-managed; description column is the user's
    to edit — it is round-tripped through load_registry)."""
    path = registry_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["| tag | description | aliases |", "|---|---|---|"]
    for tag, info in registry.items():
        desc = (info.get("description") or "").replace("|", "/").strip()
        aliases = ", ".join(info.get("aliases") or [])
        rows.append(f"| {tag} | {desc} | {aliases} |")
    table = "\n".join(rows)
    body = (
        "---\n"
        "Type:\n- Reference\n"
        "tags:\n- MOC\n"
        "kb-generated: true\n"
        "---\n"
        "# Tag Registry\n"
        "---\n\n"
        "This is the **official tag registry** PaperRoach uses for paper notes. "
        "During builds, the LLM is asked to reuse these tags first. New tags are "
        "added here automatically when no existing tag fits. You can freely edit "
        "`description`; every spelling listed in `aliases` is normalized to the "
        "canonical tag on the left.\n\n"
        f"{REGISTRY_START}\n{table}\n{REGISTRY_END}\n"
    )
    managed = f"{REGISTRY_START}\n{table}\n{REGISTRY_END}"
    existing = _read_text_tolerant(path) if path.exists() else ""
    start_count = existing.count(REGISTRY_START)
    end_count = existing.count(REGISTRY_END)
    if start_count == 1 and end_count == 1:
        # Preserve any prose the user added around the managed table.
        pattern = re.escape(REGISTRY_START) + r".*?" + re.escape(REGISTRY_END)
        new, replacements = re.subn(
            pattern,
            lambda _m: managed,
            existing,
            count=1,
            flags=re.DOTALL,
        )
        if replacements != 1:
            print(
                f"  ! Tag Registry block in '{path.name}' has markers out of "
                "order; skipping update.",
                flush=True,
            )
            return path
    elif start_count or end_count:
        print(
            f"  ! Tag Registry block in '{path.name}' has {start_count} start "
            f"marker(s) and {end_count} end marker(s); skipping update.",
            flush=True,
        )
        return path
    elif existing:
        new = existing.rstrip() + f"\n\n{managed}\n"
    else:
        new = body
    write_text_atomic(path, new)
    return path


def normalize(tag: str) -> str:
    """Canonical spelling: lowercase, hyphen-separated, ASCII plus Hangul."""
    tag = str(tag).strip().lstrip("#").lower()
    tag = re.sub(r"[\s_]+", "-", tag)
    tag = re.sub(r"[^0-9a-z\uac00-\ud7a3\-/]", "", tag)
    tag = re.sub(r"-{2,}", "-", tag)
    return tag.strip("-")


def _squash(tag: str) -> str:
    """Spelling-insensitive key: '' + no separators (computer-vision == computervision)."""
    return re.sub(r"[-/]", "", normalize(tag))


def alias_index(registry: dict[str, dict]) -> dict[str, str]:
    """{squashed alias or canonical: canonical}"""
    index: dict[str, str] = {}
    for tag, info in registry.items():
        index[_squash(tag)] = tag
        for alias in info.get("aliases") or []:
            index.setdefault(_squash(alias), tag)
    return index


def canonicalize(
    tags: list[str], registry: dict[str, dict], limit: int = MAX_TAGS_PER_NOTE
) -> list[str]:
    """Map tags onto the vocabulary; unknown tags pass through normalised."""
    index = alias_index(registry)
    out: list[str] = []
    for raw in tags or []:
        tag = normalize(raw)
        if not tag:
            continue
        tag = index.get(_squash(tag), tag)
        if tag not in out:
            out.append(tag)
        if len(out) >= limit:
            break
    return out


def register_new(config: Config, registry: dict[str, dict], tags: list[str]) -> int:
    """Append vocabulary entries for genuinely new tags; returns how many."""
    index = alias_index(registry)
    added = 0
    for tag in tags:
        tag = normalize(tag)
        if not tag or _squash(tag) in index:
            continue
        registry[tag] = {"description": "", "aliases": []}
        index[_squash(tag)] = tag
        added += 1
    if added:
        save_registry(config, registry)
    return added
