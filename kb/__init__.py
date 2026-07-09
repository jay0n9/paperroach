"""PaperRoach: local-first paper knowledge pipeline for Obsidian.

A two-pass, VRAM-aware pipeline for an 8GB GPU (RTX 3070 Ti):

    PASS A  ── resident LLM (Qwen3 8B)      ── ingest -> metadata -> chunk
       ⇄    ── Ollama model swap (once)     ── avoid 8GB co-residency
    PASS B  ── resident embedder (bge-m3)   ── embed -> store -> link -> note

See README.md for the full architecture diagram.
"""

__version__ = "0.1.0"
