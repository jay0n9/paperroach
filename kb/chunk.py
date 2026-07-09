"""Stage ③ — header-aware chunking.

Strategy: split on Markdown headers first (section boundaries are the most
semantically meaningful break), then window any over-long section into
overlapping pieces, preferring paragraph / sentence boundaries. Each chunk is
prefixed with its header path so the embedding (and any retrieved context)
carries section context.
"""
from __future__ import annotations

import re

from kb.config import Config
from kb.models import Chunk

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
# Fenced code blocks must not be split mid-fence; we track fence state.
_FENCE_RE = re.compile(r"^(```|~~~)")


def chunk_markdown(markdown: str, config: Config) -> list[Chunk]:
    sections = _split_sections(markdown)
    chunks: list[Chunk] = []
    idx = 0
    for header, text in sections:
        for piece in _window(text, config.chunk_size, config.chunk_overlap):
            body = f"[{header}]\n{piece}" if header else piece
            chunks.append(Chunk(chunk_index=idx, header=header, text=body))
            idx += 1
    if not chunks:  # e.g. a header-less note shorter than nothing
        for piece in _window(markdown.strip(), config.chunk_size, config.chunk_overlap):
            chunks.append(Chunk(chunk_index=idx, header="", text=piece))
            idx += 1
    return chunks


def _split_sections(markdown: str) -> list[tuple[str, str]]:
    """Return [(header_path, body_text), ...] respecting code fences.

    PDF→Markdown conversion sometimes emits a stray, never-closed fence; if
    the document ends mid-fence, every later header would be swallowed into
    one giant section, so we reparse ignoring fences entirely.
    """
    sections, balanced = _split_sections_pass(markdown, honor_fences=True)
    if not balanced:
        sections, _ = _split_sections_pass(markdown, honor_fences=False)
    return sections


def _split_sections_pass(
    markdown: str, *, honor_fences: bool
) -> tuple[list[tuple[str, str]], bool]:
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []  # (level, title)
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        if any(line.strip() for line in buf):
            header = " > ".join(title for _, title in stack)
            sections.append((header, "\n".join(buf).strip()))
        buf.clear()

    for line in markdown.splitlines():
        if honor_fences and _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            buf.append(line)
            continue
        m = _HEADER_RE.match(line) if not in_fence else None
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
        else:
            buf.append(line)
    flush()
    return sections, not in_fence


def _window(text: str, size: int, overlap: int) -> list[str]:
    if size < 1:
        raise ValueError(f"chunk size must be at least 1 (got {size})")
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    overlap = max(0, min(overlap, size - 1))
    out: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # Prefer a paragraph break, then a newline, then a sentence end,
            # but only in the latter part of the window so chunks stay sized.
            lo = start + int(size * 0.6)
            brk = text.rfind("\n\n", lo, end)
            if brk == -1:
                brk = text.rfind("\n", lo, end)
            if brk == -1:
                brk = text.rfind(". ", lo, end)
            if brk != -1 and brk > start:
                end = brk + 1
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= n:
            break
        new_start = end - overlap
        # Guard against pathological no-progress loops.
        start = new_start if new_start > start else end
    return out
