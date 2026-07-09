"""Zotero integration.

* Auto-detect the Zotero data directory (honouring a custom ``dataDir`` set in
  the Zotero profile, e.g. ``D:\\Zotero``).
* Enumerate attachment PDFs under ``storage/``.
* Best-effort metadata enrichment: read title / authors / year / venue / DOI /
  tags straight from ``zotero.sqlite`` (read-only) so generated notes use
  Zotero's clean bibliographic data instead of LLM guesses from
  possibly-OCR'd text.

All DB access is read-only and defensive: any failure (locked DB, schema
variance, non-Zotero path) simply returns ``None`` and the pipeline falls back
to LLM-extracted metadata.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

from kb.config import Config
from kb.models import PaperMetadata

_DATADIR_RE = re.compile(r'extensions\.zotero\.dataDir",\s*"(.*?)"')
_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")


# --------------------------------------------------------------------------- #
#  Locating Zotero
# --------------------------------------------------------------------------- #
def find_data_dir(config: Config) -> Path | None:
    """Resolve the Zotero data directory.

    Order: explicit config -> profile ``prefs.js`` (``dataDir``) -> ~/Zotero.
    """
    if config.zotero_dir:
        p = Path(config.zotero_dir).expanduser()
        return p if (p / "zotero.sqlite").exists() else None

    appdata = os.environ.get("APPDATA")
    if appdata:
        profiles = Path(appdata) / "Zotero" / "Zotero" / "Profiles"
        for prefs in profiles.glob("*/prefs.js"):
            try:
                text = prefs.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            m = _DATADIR_RE.search(text)
            if m:
                # prefs.js stores JS string escapes: "E:\\Zotero" -> E:\Zotero
                p = Path(m.group(1).replace("\\\\", "\\"))
                if (p / "zotero.sqlite").exists():
                    return p

    default = Path.home() / "Zotero"
    return default if (default / "zotero.sqlite").exists() else None


def storage_pdfs(data_dir: Path) -> list[Path]:
    """All attachment PDFs (Zotero stores them as storage/<KEY>/<file>.pdf)."""
    storage = data_dir / "storage"
    if not storage.exists():
        return []
    return sorted(storage.glob("*/*.pdf"))


def is_zotero_pdf(data_dir: Path | None, path: Path) -> bool:
    if data_dir is None:
        return False
    try:
        path.resolve().relative_to((data_dir / "storage").resolve())
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
#  Metadata
# --------------------------------------------------------------------------- #
def _open_readonly(db: Path) -> tuple[sqlite3.Connection | None, Path | None]:
    """Open the Zotero DB read-only WITHOUT ever blocking on its live lock.

    ``mode=ro`` on the live file can block indefinitely while Zotero holds the
    handle, so it is only used with a short timeout. ``immutable=1`` (instant,
    lock-free) is safe only when no write is possibly in flight — i.e. no
    ``-wal`` *and* no ``-journal`` sidecar; reading a mid-write DB under
    immutable can silently return corrupt data rather than raise.

    Otherwise we take a consistent snapshot via sqlite's online backup API
    (which understands WAL/journal state), falling back to a raw file copy.

    Returns ``(connection, tempdir)``; ``tempdir`` must be removed by the caller.
    """
    sidecars = [Path(str(db) + ext) for ext in ("-wal", "-journal")]
    if not any(p.exists() for p in sidecars):
        try:
            con = sqlite3.connect(
                f"file:{db.as_posix()}?immutable=1", uri=True, timeout=2
            )
            return con, None
        except sqlite3.Error:
            pass
    return _snapshot_and_open(db)


def _snapshot_and_open(db: Path) -> tuple[sqlite3.Connection | None, Path | None]:
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="kb_zot_"))
    except OSError:
        return None, None
    dst = tmpdir / "zotero.sqlite"
    # Preferred: sqlite's online backup API — yields a transactionally
    # consistent snapshot even while Zotero is writing.
    try:
        src = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            snap = sqlite3.connect(str(dst))
            try:
                src.backup(snap)
            finally:
                snap.close()
        finally:
            src.close()
        con = sqlite3.connect(f"file:{dst.as_posix()}?mode=ro", uri=True, timeout=2)
        return con, tmpdir
    except (sqlite3.Error, OSError):
        pass
    # Fallback: raw copy of the DB + sidecars (best effort, may be torn if a
    # checkpoint lands mid-copy — sqlite errors are caught by the caller).
    try:
        shutil.copy2(db, dst)
        for ext in ("-wal", "-shm", "-journal"):
            side = Path(str(db) + ext)
            if side.exists():
                shutil.copy2(side, str(dst) + ext)
        con = sqlite3.connect(f"file:{dst.as_posix()}?mode=ro", uri=True, timeout=2)
        return con, tmpdir
    except (sqlite3.Error, OSError):
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, None


def read_metadata(data_dir: Path, pdf_path: Path) -> dict | None:
    """Return bibliographic metadata for a storage PDF, or None."""
    db = data_dir / "zotero.sqlite"
    if not db.exists():
        return None
    key = pdf_path.parent.name  # storage/<KEY>/file.pdf  ->  attachment item key
    con, tmpdir = _open_readonly(db)
    if con is None:
        return None
    try:
        cur = con.cursor()
        att = cur.execute("SELECT itemID FROM items WHERE key = ?", (key,)).fetchone()
        if not att:
            return None
        att_id = att[0]
        par = cur.execute(
            "SELECT parentItemID FROM itemAttachments WHERE itemID = ?", (att_id,)
        ).fetchone()
        target = par[0] if par and par[0] else att_id

        item_type = _item_type(cur, target)
        title = _field(cur, target, "title")
        date = _field(cur, target, "date")
        year = None
        if date:
            m = _YEAR_RE.search(date)
            year = int(m.group(0)) if m else None

        authors = []
        for fn, ln in cur.execute(
            "SELECT c.firstName, c.lastName FROM itemCreators ic "
            "JOIN creators c ON c.creatorID = ic.creatorID "
            "WHERE ic.itemID = ? ORDER BY ic.orderIndex",
            (target,),
        ).fetchall():
            name = " ".join(x for x in (fn, ln) if x).strip()
            if name:
                authors.append(name)

        tags = []
        for (name,) in cur.execute(
            "SELECT t.name FROM itemTags it JOIN tags t ON t.tagID = it.tagID "
            "WHERE it.itemID = ?",
            (target,),
        ).fetchall():
            tag = _clean_tag(name)
            if tag:
                tags.append(tag)

        url = _field(cur, target, "url")
        doi = _field(cur, target, "DOI") or _field(cur, target, "doi")
        volume = _field(cur, target, "volume")
        issue = _field(cur, target, "issue")
        pages = _field(cur, target, "pages")
        publisher = _field(cur, target, "publisher")
        venue = _first_field(
            cur,
            target,
            [
                "publicationTitle",
                "proceedingsTitle",
                "conferenceName",
                "bookTitle",
                "seriesTitle",
                "websiteTitle",
                "university",
                "publisher",
            ],
        )

        if not (title or authors or year or tags or url or venue or doi):
            return None
        return {
            "title": title,
            "authors": authors,
            "year": year,
            "tags": tags,
            "url": url,
            "venue": venue,
            "venue_type": item_type,
            "doi": doi,
            "volume": volume,
            "issue": issue,
            "pages": pages,
            "publisher": publisher,
        }
    except sqlite3.Error:
        return None
    finally:
        con.close()
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _field(cur: sqlite3.Cursor, item_id: int, field_name: str) -> str | None:
    row = cur.execute(
        "SELECT v.value FROM itemData d "
        "JOIN itemDataValues v ON v.valueID = d.valueID "
        "JOIN fields f ON f.fieldID = d.fieldID "
        "WHERE d.itemID = ? AND f.fieldName = ?",
        (item_id, field_name),
    ).fetchone()
    return row[0] if row and row[0] else None


def _first_field(
    cur: sqlite3.Cursor, item_id: int, field_names: list[str]
) -> str | None:
    for name in field_names:
        value = _field(cur, item_id, name)
        if value:
            return value
    return None


def _item_type(cur: sqlite3.Cursor, item_id: int) -> str | None:
    row = cur.execute(
        "SELECT it.typeName FROM items i "
        "JOIN itemTypes it ON it.itemTypeID = i.itemTypeID "
        "WHERE i.itemID = ?",
        (item_id,),
    ).fetchone()
    return row[0] if row and row[0] else None


def _clean_tag(tag: str) -> str:
    tag = re.sub(r"\s+", "-", tag.strip().lstrip("#").lower())
    tag = re.sub(r"[^0-9a-z\uac00-\ud7a3\-_/]", "", tag)
    tag = re.sub(r"-{2,}", "-", tag)  # never emit '---' (breaks naive YAML readers)
    return tag.strip("-")


def enrich(metadata: PaperMetadata, source_path: Path, config: Config) -> PaperMetadata:
    """Override metadata fields with Zotero's, when available. Best-effort."""
    if not config.zotero_enrich:
        return metadata
    try:
        data_dir = find_data_dir(config)
        if not is_zotero_pdf(data_dir, source_path):
            return metadata
        info = read_metadata(data_dir, source_path)
    except Exception:
        return metadata
    if not info:
        return metadata

    if info.get("title"):
        metadata.title = info["title"]
    if info.get("authors"):
        metadata.authors = info["authors"]
    if info.get("year"):
        metadata.year = info["year"]
    if info.get("tags"):
        # Zotero tags first, then any LLM tags not already present.
        metadata.tags = list(dict.fromkeys([*info["tags"], *metadata.tags]))
    if info.get("url"):
        metadata.source_url = info["url"]
    if info.get("venue"):
        metadata.venue = info["venue"]
    if info.get("venue_type"):
        metadata.venue_type = info["venue_type"]
    if info.get("doi"):
        metadata.doi = info["doi"]
    if info.get("volume"):
        metadata.volume = info["volume"]
    if info.get("issue"):
        metadata.issue = info["issue"]
    if info.get("pages"):
        metadata.pages = info["pages"]
    if info.get("publisher"):
        metadata.publisher = info["publisher"]
    return metadata
