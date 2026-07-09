"""Shared dataclasses passed between pipeline stages."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PaperMetadata:
    """Structured metadata extracted by the LLM (stage ②)."""

    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    summary: str = ""
    key_contributions: list[str] = field(default_factory=list)
    methods: str = ""
    tags: list[str] = field(default_factory=list)
    source_url: str = ""  # e.g. Zotero's URL field; falls back to file path
    venue: str = ""       # journal, conference, proceedings, book, etc.
    venue_type: str = ""  # e.g. journalArticle, conferencePaper
    doi: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""


@dataclass
class PaperAnalysis:
    """Rich English analysis used to render a detailed Source Material note."""

    tl_dr: str = ""
    problem_motivation: str = ""
    approach: str = ""  # may contain Markdown subsections/bullets
    key_results: str = ""
    contributions: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    takeaways: str = ""
    subject: str = ""  # Knowledge Library domain folder for this paper's concepts
    # [{name, relation, explanation, why_it_matters}]
    concepts: list[dict] = field(default_factory=list)


@dataclass
class PaperClassification:
    """Primary paper domain used for filing the paper note."""

    primary_domain: str = ""
    subdomain: str = ""
    secondary_domains: list[str] = field(default_factory=list)
    contribution_type: str = ""
    methods: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float | None = None


@dataclass
class Chunk:
    """A header-aware text chunk (stage ③)."""

    chunk_index: int
    header: str
    text: str


@dataclass
class Document:
    """Everything we know about one input, threaded through both passes."""

    doc_id: str
    source_path: Path
    kind: str  # "pdf" | "note"
    markdown: str
    metadata: PaperMetadata
    chunks: list[Chunk] = field(default_factory=list)

    # Filled in before storage so related-linking is order-independent.
    note_path: Path | None = None
    link_target: str | None = None  # Obsidian wikilink basename (no ".md")

    # Filled in during the linking stage (⑥).
    related: list[str] = field(default_factory=list)  # list of link targets

    # Filled in during PASS A (rich English analysis for the note body).
    analysis: "PaperAnalysis | None" = None

    # Filled in during PASS A by the paper-domain classifier. This is distinct
    # from analysis.subject, which is the concept-note Knowledge Library domain.
    classification: "PaperClassification | None" = None

    # Filled in during PASS B (embedding of the metadata summary).
    summary_vector: list[float] | None = None

    # Display equations ($$...$$) extracted verbatim from the source markdown
    # (populated when a math-aware ingester like nougat is used).
    equations: list[str] = field(default_factory=list)
    equations_integrated: bool = False  # equations woven into the Approach prose


def doc_id_for(source_path: Path) -> str:
    """Stable id derived from the absolute source path.

    Re-running the pipeline on the same file updates the same DB rows / note.
    """
    key = str(source_path.resolve()).lower()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def content_hash_for(source_path: Path) -> str | None:
    """sha1 of the file bytes — catches the *same* PDF stored under two paths
    (e.g. a duplicate Zotero attachment), which path-based ids cannot.

    Returns None if the file cannot be read.
    """
    try:
        h = hashlib.sha1()
        with open(source_path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None
