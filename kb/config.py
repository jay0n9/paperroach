"""Configuration loading and merging.

Precedence (highest first):
    1. explicit CLI overrides (dict passed to ``load_config``)
    2. environment variables (``KB_*``)
    3. a ``kb.toml`` file (``KB_CONFIG`` env, ./kb.toml, or <vault>/kb.toml)
    4. built-in defaults
"""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


# Map of config field -> environment variable name.
_ENV = {
    "vault_path": "KB_VAULT",
    "references_dir": "KB_REFERENCES_DIR",
    "kb_dir": "KB_DIR",
    "ollama_host": "KB_OLLAMA_HOST",
    "llm_model": "KB_LLM_MODEL",
    "embed_model": "KB_EMBED_MODEL",
    "keep_alive": "KB_KEEP_ALIVE",
    "ingester": "KB_INGESTER",
    "zotero_dir": "KB_ZOTERO_DIR",
}

_BOOL_FIELDS = {
    "llm_think",
    "rewrite_source_notes",
    "zotero_enrich",
    "create_concept_notes",
    "references_by_subject",
    "references_by_subdomain",
}
_INT_FIELDS = {
    "llm_num_ctx",
    "llm_seed",
    "embed_dim",
    "meta_input_chars",
    "analysis_input_chars",
    "chunk_size",
    "chunk_overlap",
    "related_top_k",
    "rag_top_k",
    "ocr_dpi",
    "nougat_batchsize",
    "watch_interval",
}


@dataclass
class Config:
    # ── paths ────────────────────────────────────────────────────────
    vault_path: Path
    references_dir: str = "References"
    knowledge_library_dir: str = "6 - Knowledge Library"
    tags_dir: str = "3 - Tags"  # where the Tag Registry note lives
    kb_dir: str = ".kb"

    # ── Ollama ───────────────────────────────────────────────────────
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "qwen3:8b"
    llm_think: bool = False
    llm_num_ctx: int = 8192
    llm_seed: int = 7
    embed_model: str = "bge-m3"
    embed_dim: int = 1024
    keep_alive: str = "30m"

    # ── LLM metadata + analysis extraction ───────────────────────────
    meta_input_chars: int = 12000
    analysis_input_chars: int = 12000
    note_language: str = "English"  # language of the generated note body

    # ── chunking ─────────────────────────────────────────────────────
    chunk_size: int = 1200
    chunk_overlap: int = 150

    # ── retrieval ────────────────────────────────────────────────────
    related_top_k: int = 5
    rag_top_k: int = 8
    answer_language: str = "English"

    # ── behaviour ────────────────────────────────────────────────────
    ingester: str = "pymupdf4llm"
    ocr_dpi: int = 200
    nougat_batchsize: int = 2  # >0 forces nougat onto the GPU (0 = CPU fallback)
    rewrite_source_notes: bool = True
    create_concept_notes: bool = True  # auto-create Knowledge Library notes
    # File paper notes into <references_dir>/<Subject>/ (the same domain the
    # LLM picks for the paper's concepts) instead of one flat folder.
    references_by_subject: bool = True
    # If a paper-domain classifier returns a subdomain, nest paper notes under
    # <references_dir>/<Domain>/<Subdomain>/.
    references_by_subdomain: bool = True

    # ── Zotero integration ───────────────────────────────────────────
    zotero_dir: str = ""          # "" → auto-detect from the Zotero profile
    zotero_enrich: bool = True    # prefer Zotero DB metadata (title/authors/year/tags)
    watch_interval: int = 15      # seconds between `kb watch` scans

    # ── derived paths ────────────────────────────────────────────────
    @property
    def kb_path(self) -> Path:
        return self.vault_path / self.kb_dir

    @property
    def references_path(self) -> Path:
        return self.vault_path / self.references_dir

    @property
    def knowledge_library_path(self) -> Path:
        return self.vault_path / self.knowledge_library_dir

    def ensure_dirs(self) -> None:
        self.kb_path.mkdir(parents=True, exist_ok=True)
        self.references_path.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
#  Loading helpers
# --------------------------------------------------------------------------- #
def _find_config_file(overrides: dict) -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("KB_CONFIG"):
        candidates.append(Path(os.environ["KB_CONFIG"]))
    candidates.append(Path.cwd() / "kb.toml")
    # A vault may carry its own kb.toml; consider it if we know the vault.
    vault = overrides.get("vault_path") or os.environ.get("KB_VAULT")
    if vault:
        candidates.append(Path(vault) / "kb.toml")
    for c in candidates:
        if c.is_file():
            return c
    return None


def _coerce(field_name: str, value):
    if field_name == "vault_path":
        return Path(value).expanduser()
    if field_name in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if field_name in _INT_FIELDS:
        return int(value)
    return value


def load_config(overrides: dict | None = None) -> Config:
    """Build a :class:`Config`, merging file / env / CLI overrides.

    ``overrides`` keys mirror :class:`Config` field names. ``None`` values are
    ignored so callers can pass argparse results verbatim.
    """
    overrides = {k: v for k, v in (overrides or {}).items() if v is not None}
    valid = {f.name for f in fields(Config)}

    merged: dict = {}

    # 3. file
    cfg_file = _find_config_file(overrides)
    if cfg_file is not None:
        with cfg_file.open("rb") as fh:
            data = tomllib.load(fh)
        for k, v in data.items():
            if k in valid:
                merged[k] = v
            else:
                print(
                    f"kb: warning: unknown key '{k}' in {cfg_file} (ignored)",
                    file=sys.stderr,
                )

    # 2. environment
    for field_name, env_name in _ENV.items():
        if os.environ.get(env_name):
            merged[field_name] = os.environ[env_name]

    # 1. CLI overrides
    for k, v in overrides.items():
        if k in valid:
            merged[k] = v

    if "vault_path" not in merged:
        raise ConfigError(
            "No vault path configured. Pass --vault, set KB_VAULT, or add "
            "vault_path to kb.toml (see kb.example.toml)."
        )

    coerced = {k: _coerce(k, v) for k, v in merged.items()}
    cfg = Config(**coerced)

    if not cfg.vault_path.exists():
        raise ConfigError(f"Vault path does not exist: {cfg.vault_path}")
    return cfg


class ConfigError(RuntimeError):
    """Raised for user-facing configuration problems."""
