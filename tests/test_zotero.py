import sqlite3
import tempfile
import unittest
from pathlib import Path

from kb.config import Config
from kb.models import PaperMetadata
from kb import zotero


def _make_zotero_fixture(root: Path) -> tuple[Path, Path]:
    data_dir = root / "Zotero"
    pdf = data_dir / "storage" / "ATTACH1" / "paper.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4\n")
    con = sqlite3.connect(data_dir / "zotero.sqlite")
    try:
        cur = con.cursor()
        cur.executescript(
            """
            CREATE TABLE itemTypes (
                itemTypeID INTEGER PRIMARY KEY,
                typeName TEXT
            );
            CREATE TABLE items (
                itemID INTEGER PRIMARY KEY,
                key TEXT,
                itemTypeID INTEGER
            );
            CREATE TABLE itemAttachments (
                itemID INTEGER PRIMARY KEY,
                parentItemID INTEGER
            );
            CREATE TABLE fields (
                fieldID INTEGER PRIMARY KEY,
                fieldName TEXT
            );
            CREATE TABLE itemDataValues (
                valueID INTEGER PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE itemData (
                itemID INTEGER,
                fieldID INTEGER,
                valueID INTEGER
            );
            CREATE TABLE creators (
                creatorID INTEGER PRIMARY KEY,
                firstName TEXT,
                lastName TEXT
            );
            CREATE TABLE itemCreators (
                itemID INTEGER,
                creatorID INTEGER,
                orderIndex INTEGER
            );
            CREATE TABLE tags (
                tagID INTEGER PRIMARY KEY,
                name TEXT
            );
            CREATE TABLE itemTags (
                itemID INTEGER,
                tagID INTEGER
            );
            """
        )
        cur.executemany(
            "INSERT INTO itemTypes VALUES (?, ?)",
            [(1, "conferencePaper"), (2, "attachment")],
        )
        cur.executemany(
            "INSERT INTO items VALUES (?, ?, ?)",
            [(10, "PARENT1", 1), (20, "ATTACH1", 2)],
        )
        cur.execute("INSERT INTO itemAttachments VALUES (?, ?)", (20, 10))
        fields = [
            "title",
            "date",
            "url",
            "DOI",
            "volume",
            "issue",
            "pages",
            "publisher",
            "conferenceName",
            "extra",
        ]
        cur.executemany(
            "INSERT INTO fields VALUES (?, ?)",
            [(i + 1, name) for i, name in enumerate(fields)],
        )
        values = {
            "title": "User-Led VR Relaxation",
            "date": "Proceedings published 2024-05-11",
            "url": "https://example.org/paper",
            "DOI": "10.1145/example",
            "volume": "12",
            "issue": "3",
            "pages": "101-118",
            "publisher": "ACM",
            "conferenceName": "CHI Conference on Human Factors in Computing Systems",
            "extra": (
                "Citation Key: lovelace2024\n"
                "PaperRoach Domain: HCI\n"
                "PaperRoach Subdomain: Health & Wellbeing"
            ),
        }
        for value_id, (field_name, value) in enumerate(values.items(), 1):
            field_id = fields.index(field_name) + 1
            cur.execute("INSERT INTO itemDataValues VALUES (?, ?)", (value_id, value))
            cur.execute("INSERT INTO itemData VALUES (?, ?, ?)", (10, field_id, value_id))
        cur.executemany(
            "INSERT INTO creators VALUES (?, ?, ?)",
            [(1, "Ada", "Lovelace"), (2, "Grace", "Hopper")],
        )
        cur.executemany(
            "INSERT INTO itemCreators VALUES (?, ?, ?)",
            [(10, 1, 0), (10, 2, 1)],
        )
        cur.executemany(
            "INSERT INTO tags VALUES (?, ?)",
            [(1, "#HCI Study"), (2, "VR/AR"), (3, "bad --- tag!")],
        )
        cur.executemany(
            "INSERT INTO itemTags VALUES (?, ?)",
            [(10, 1), (10, 2), (10, 3)],
        )
        con.commit()
    finally:
        con.close()
    return data_dir, pdf


class ZoteroTests(unittest.TestCase):
    def test_storage_pdfs_matches_pdf_suffix_case_insensitively(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "Zotero"
            lower = data_dir / "storage" / "LOWER" / "paper.pdf"
            upper = data_dir / "storage" / "UPPER" / "paper.PDF"
            ignored = data_dir / "storage" / "TEXT" / "note.txt"
            for path in (lower, upper, ignored):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")

            found = zotero.storage_pdfs(data_dir)

            self.assertEqual({p.name for p in found}, {"paper.pdf", "paper.PDF"})

    def test_read_metadata_uses_parent_item_for_storage_attachment(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir, pdf = _make_zotero_fixture(Path(td))

            info = zotero.read_metadata(data_dir, pdf)

            self.assertIsNotNone(info)
            assert info is not None
            self.assertEqual(info["title"], "User-Led VR Relaxation")
            self.assertEqual(info["authors"], ["Ada Lovelace", "Grace Hopper"])
            self.assertEqual(info["year"], 2024)
            self.assertEqual(info["tags"], ["hci-study", "vr/ar", "bad-tag"])
            self.assertEqual(
                info["venue"],
                "CHI Conference on Human Factors in Computing Systems",
            )
            self.assertEqual(info["venue_type"], "conferencePaper")
            self.assertEqual(info["doi"], "10.1145/example")
            self.assertEqual(info["volume"], "12")
            self.assertEqual(info["issue"], "3")
            self.assertEqual(info["pages"], "101-118")
            self.assertEqual(info["publisher"], "ACM")
            self.assertEqual(info["primary_domain"], "HCI")
            self.assertEqual(info["subdomain"], "Health & Wellbeing")

    def test_enrich_merges_zotero_metadata_without_dropping_llm_tags(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir, pdf = _make_zotero_fixture(root)
            config = Config(
                vault_path=root / "vault",
                kb_dir=".kb",
                zotero_dir=str(data_dir),
            )
            metadata = PaperMetadata(
                title="LLM Guess",
                authors=["Unknown"],
                year=2020,
                tags=["paper", "personal-note", "hci-study"],
            )

            enriched = zotero.enrich(metadata, pdf, config)

            self.assertEqual(enriched.title, "User-Led VR Relaxation")
            self.assertEqual(enriched.authors, ["Ada Lovelace", "Grace Hopper"])
            self.assertEqual(enriched.year, 2024)
            self.assertEqual(
                enriched.tags,
                ["hci-study", "vr/ar", "bad-tag", "paper", "personal-note"],
            )
            self.assertEqual(enriched.source_url, "https://example.org/paper")
            self.assertEqual(
                enriched.venue,
                "CHI Conference on Human Factors in Computing Systems",
            )
            self.assertEqual(enriched.venue_type, "conferencePaper")
            self.assertEqual(enriched.doi, "10.1145/example")
            self.assertEqual(enriched.primary_domain, "HCI")
            self.assertEqual(enriched.subdomain, "Health & Wellbeing")


if __name__ == "__main__":
    unittest.main()
