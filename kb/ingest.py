"""Stage ① — input -> Markdown.

* ``.pdf``  -> Markdown via pymupdf4llm (CPU) or, optionally, docling.
              Scanned PDFs (no text layer) automatically fall back to OCR
              (rapidocr-onnxruntime, CPU). Force OCR with ``ingester = "ocr"``.
* ``.md``   -> read as-is.

Upgrade path noted in the design: swap the backend for docling / GROBID for
higher-fidelity scientific PDF parsing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from kb.config import Config

PDF_SUFFIXES = {".pdf"}
NOTE_SUFFIXES = {".md", ".markdown"}
SUPPORTED_SUFFIXES = PDF_SUFFIXES | NOTE_SUFFIXES


class IngestError(RuntimeError):
    pass


def kind_of(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PDF_SUFFIXES:
        return "pdf"
    if suffix in NOTE_SUFFIXES:
        return "note"
    raise IngestError(f"Unsupported file type: {path.name}")


def ingest(path: Path, config: Config) -> str:
    """Return the Markdown content of ``path``."""
    kind = kind_of(path)
    if kind == "note":
        return _read_text(path)
    if config.ingester == "docling":
        return _pdf_to_markdown_docling(path)
    if config.ingester == "ocr":
        return _pdf_to_markdown_ocr(path, config)
    if config.ingester == "nougat":
        # Nougat is best-effort: a broken install (blocked DLLs, missing CUDA)
        # or a parse failure must not sink the whole batch — fall back to the
        # standard ingester and just lose the LaTeX equations for this file.
        try:
            return _pdf_to_markdown_nougat(path, config)
        except IngestError as exc:
            print(
                f"      ! nougat failed ({exc}); falling back to pymupdf4llm …",
                flush=True,
            )
            return _pdf_to_markdown_pymupdf(path, config)
    return _pdf_to_markdown_pymupdf(path, config)


def _read_text(path: Path) -> str:
    # UTF-16 first, by BOM: PowerShell 5.1 redirects write UTF-16 LE, and many
    # of those byte sequences decode "successfully" (as mojibake) under cp949,
    # so the fallback chain below would never see an error for them.
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")  # dispatches on the BOM
    # utf-8-sig decodes both BOM and BOM-less UTF-8 (stripping any BOM), so it
    # must precede the legacy cp949 fallback; a stray BOM would otherwise leak
    # into the first heading and break header-aware chunking.
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        # A BOM-less UTF-16 file can also decode under cp949 without error;
        # the giveaway is embedded NULs, which no real note contains.
        if "\x00" in text:
            continue
        return text
    # Last resort: don't crash on a stray byte.
    return raw.decode("utf-8", errors="replace")


def _pdf_to_markdown_pymupdf(path: Path, config: Config) -> str:
    # Cheap probe first: a scanned PDF has no text layer, and running the slow
    # pymupdf4llm layout pass on one can take minutes. Skip straight to OCR.
    if not _has_text_layer(path):
        print("      · no text layer (scanned PDF); using OCR …", flush=True)
        return _pdf_to_markdown_ocr(path, config)
    try:
        import pymupdf4llm
    except ModuleNotFoundError as exc:
        raise IngestError(
            "pymupdf4llm is required for PDF ingestion. Install it with:\n"
            "    pip install pymupdf4llm"
        ) from exc
    md = None
    try:
        # use_ocr=False: we OCR scanned PDFs ourselves (above). pymupdf4llm's
        # own internal rapidocr wrapper crashes on empty OCR results, and a
        # text-layer PDF doesn't need it anyway.
        md = pymupdf4llm.to_markdown(str(path), use_ocr=False)
        if isinstance(md, list):  # page_chunks=True shape, just in case
            md = "\n\n".join(p.get("text", "") for p in md)
    except Exception as exc:
        print(f"      · pymupdf4llm failed ({exc}); using plain text …", flush=True)
        md = None
    if md and md.strip():
        return md
    # Text layer exists, so plain per-page extraction is clean and reliable.
    return _pdf_plain_text(path, config)


def _pdf_plain_text(path: Path, config: Config) -> str:
    """Fallback: extract the raw text layer page-by-page (no layout/OCR)."""
    import pymupdf

    doc = pymupdf.open(str(path))
    try:
        parts = [doc[i].get_text().strip() for i in range(doc.page_count)]
    finally:
        doc.close()
    md = "\n\n".join(p for p in parts if p)
    if md.strip():
        return md
    return _pdf_to_markdown_ocr(path, config)


def _has_text_layer(path: Path, threshold: int = 50) -> bool:
    """Fast check: does the PDF contain an extractable text layer?"""
    try:
        import pymupdf
    except ModuleNotFoundError:
        return True  # can't probe cheaply; let pymupdf4llm try
    try:
        doc = pymupdf.open(str(path))
    except Exception:
        return True
    try:
        total = 0
        for i in range(doc.page_count):
            total += len(doc[i].get_text().strip())
            if total >= threshold:
                return True
        return False
    finally:
        doc.close()


def _pdf_to_markdown_ocr(path: Path, config: Config) -> str:
    """OCR a scanned PDF page-by-page with rapidocr-onnxruntime (CPU)."""
    try:
        import pymupdf
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise IngestError("PyMuPDF is required for OCR ingestion.") from exc
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ModuleNotFoundError as exc:
        raise IngestError(
            f"'{path.name}' has no text layer (scanned PDF) and OCR support is "
            "not installed. Install it with:\n"
            "    pip install rapidocr_onnxruntime"
        ) from exc

    engine = RapidOCR()
    doc = pymupdf.open(str(path))
    pages_md: list[str] = []
    try:
        for i in range(doc.page_count):
            print(f"      · OCR page {i + 1}/{doc.page_count}", flush=True)
            pix = doc[i].get_pixmap(dpi=config.ocr_dpi)
            result, _ = engine(pix.tobytes("png"))
            if not result:
                continue
            lines = [
                str(item[1]).strip()
                for item in result
                if item and len(item) > 1 and item[1]
            ]
            text = "\n".join(ln for ln in lines if ln)
            if text.strip():
                pages_md.append(f"## Page {i + 1}\n\n{text}")
    finally:
        doc.close()

    md = "\n\n".join(pages_md)
    if not md.strip():
        raise IngestError(f"OCR produced no text from {path.name}.")
    return md


def _pdf_to_markdown_nougat(path: Path, config: Config) -> str:
    """Math-aware ingestion: Nougat → Markdown with real LaTeX equations.

    Runs the nougat CLI in a subprocess so its model loads on the GPU only for
    the duration of parsing (isolated from the resident Ollama models). The
    Mathpix-style ``\\(...\\)`` / ``\\[...\\]`` delimiters are converted to
    Obsidian/MathJax ``$...$`` / ``$$...$$``.
    """
    try:
        import nougat  # noqa: F401  (ensure the package is importable)
    except ModuleNotFoundError as exc:
        raise IngestError(
            "nougat-ocr is required for --ingester nougat. Install it with:\n"
            "    pip install nougat-ocr"
        ) from exc
    except ImportError as exc:
        # e.g. "DLL load failed … An Application Control policy has blocked
        # this file" when Smart App Control blocks nougat's unsigned deps.
        raise IngestError(f"nougat is installed but not importable: {exc}") from exc

    # Free VRAM (unload any resident Ollama models) so nougat's GPU model fits
    # on an 8GB card; nougat runs in its own process and frees the GPU on exit.
    _unload_ollama(config)

    scripts = Path(sys.executable).parent / "Scripts"
    exe = scripts / ("nougat.exe" if os.name == "nt" else "nougat")
    nougat_cmd = str(exe) if exe.exists() else "nougat"

    tmp = Path(tempfile.mkdtemp(prefix="kb_nougat_"))
    try:
        # --batchsize > 0 is REQUIRED: nougat picks the device from `batchsize > 0`,
        # so a 0 (its low-VRAM auto-default) silently forces slow CPU inference.
        cmd = [
            nougat_cmd, str(path), "-o", str(tmp),
            "--batchsize", str(max(1, config.nougat_batchsize)),
            "--no-skipping",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2400,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise IngestError(f"nougat failed to run: {exc}") from exc
        if proc.returncode != 0:
            raise IngestError(
                f"nougat exited with {proc.returncode}: {proc.stderr[-500:]}"
            )

        outputs = sorted(tmp.glob("*.mmd"))
        if not outputs:
            raise IngestError(f"nougat produced no output for {path.name}.")
        md = outputs[0].read_text(encoding="utf-8", errors="replace")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    md = _nougat_math_to_obsidian(md)
    if not md.strip():
        raise IngestError(f"nougat extracted no text from {path.name}.")
    return md


def _unload_ollama(config: Config) -> None:
    """Evict resident Ollama models to free VRAM for nougat."""
    from kb.ollama_client import OllamaClient

    client = OllamaClient(config)
    client.unload_llm()
    client.unload_embed()


def _nougat_math_to_obsidian(md: str) -> str:
    # Mathpix-markdown delimiters -> Obsidian/MathJax dollar delimiters.
    md = md.replace("\\[", "$$").replace("\\]", "$$")
    md = md.replace("\\(", "$").replace("\\)", "$")
    return md


def _pdf_to_markdown_docling(path: Path) -> str:
    try:
        from docling.document_converter import DocumentConverter
    except ModuleNotFoundError as exc:
        raise IngestError(
            "docling is required for --ingester docling. Install it with:\n"
            "    pip install docling"
        ) from exc
    converter = DocumentConverter()
    result = converter.convert(str(path))
    md = result.document.export_to_markdown()
    if not md or not md.strip():
        raise IngestError(f"No text extracted from {path.name} (scanned PDF?).")
    return md
