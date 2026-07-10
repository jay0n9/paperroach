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
    "embed_dim": "KB_EMBED_DIM",
    "keep_alive": "KB_KEEP_ALIVE",
    "ingester": "KB_INGESTER",
    "figure_mode": "KB_FIGURE_MODE",
    "figure_backend": "KB_FIGURE_BACKEND",
    "vision_model": "KB_VISION_MODEL",
    "figure_assets_dir": "KB_FIGURE_ASSETS_DIR",
    "zotero_dir": "KB_ZOTERO_DIR",
}

_BOOL_FIELDS = {
    "llm_think",
    "rewrite_source_notes",
    "zotero_enrich",
    "create_concept_notes",
    "references_by_subject",
    "references_by_subdomain",
    "figure_include_tables",
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
    "figure_max_per_paper",
}
_FLOAT_FIELDS = {"figure_min_area_ratio", "figure_image_scale"}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_POSITIVE_INT_FIELDS = {
    "llm_num_ctx",
    "embed_dim",
    "meta_input_chars",
    "analysis_input_chars",
    "chunk_size",
    "related_top_k",
    "rag_top_k",
    "ocr_dpi",
    "watch_interval",
    "figure_max_per_paper",
}
_NONNEGATIVE_INT_FIELDS = {"chunk_overlap", "nougat_batchsize"}
_RELATIVE_DIR_FIELDS = {
    "references_dir",
    "knowledge_library_dir",
    "tags_dir",
    "figure_assets_dir",
}
_INGESTERS = {"pymupdf4llm", "ocr", "nougat", "docling"}
_FIGURE_MODES = {"off", "extract", "describe"}
_FIGURE_BACKENDS = {"docling", "pymupdf"}


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
    vision_model: str = "qwen2.5vl:7b"

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

    # Optional figure-aware PDF enrichment. It is opt-in because Docling and a
    # vision model add substantial download and processing costs.
    figure_mode: str = "off"  # "off" | "extract" | "describe"
    figure_backend: str = "docling"
    figure_assets_dir: str = "Assets/PaperRoach"
    figure_max_per_paper: int = 12
    figure_min_area_ratio: float = 0.02
    figure_image_scale: float = 2.0
    figure_include_tables: bool = False

    # ── Zotero integration ───────────────────────────────────────────
    zotero_dir: str = ""          # "" → auto-detect from the Zotero profile
    zotero_enrich: bool = True    # prefer Zotero DB metadata (title/authors/year/tags)
    watch_interval: int = 15      # seconds between `paperroach watch` scans

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

    @property
    def figure_assets_path(self) -> Path:
        return self.vault_path / self.figure_assets_dir

    def ensure_dirs(self) -> None:
        self.kb_path.mkdir(parents=True, exist_ok=True)
        self.references_path.mkdir(parents=True, exist_ok=True)
        if self.figure_mode != "off":
            self.figure_assets_path.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
#  Loading helpers
# --------------------------------------------------------------------------- #
def _find_config_file(overrides: dict) -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("KB_CONFIG"):
        explicit = Path(os.environ["KB_CONFIG"])
        if not explicit.is_file():
            raise ConfigError(f"KB_CONFIG points to a missing file: {explicit}")
        return explicit
    # A vault may carry its own kb.toml; consider it if we know the vault.
    vault = overrides.get("vault_path") or os.environ.get("KB_VAULT")
    if vault:
        candidates.append(Path(vault) / "kb.toml")
    candidates.append(Path.cwd() / "kb.toml")
    for c in candidates:
        if c.is_file():
            return c
    return None


def _path_identity(value) -> str:
    path = Path(value).expanduser()
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    return os.path.normcase(str(resolved))


def _same_path(a, b) -> bool:
    return _path_identity(a) == _path_identity(b)


def _coerce(field_name: str, value):
    if field_name == "vault_path":
        return Path(value).expanduser()
    if field_name in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
        raise ConfigError(
            f"Invalid boolean for {field_name}: {value!r}. "
            "Use true/false, yes/no, on/off, or 1/0."
        )
    if field_name in _INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"Invalid integer for {field_name}: {value!r}") from exc
    if field_name in _FLOAT_FIELDS:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"Invalid number for {field_name}: {value!r}") from exc
    return value


def _validate_config(cfg: Config) -> None:
    """Reject values that would hang the pipeline or escape the vault layout."""
    for field_name in _POSITIVE_INT_FIELDS:
        value = getattr(cfg, field_name)
        if value < 1:
            raise ConfigError(f"{field_name} must be at least 1 (got {value}).")
    for field_name in _NONNEGATIVE_INT_FIELDS:
        value = getattr(cfg, field_name)
        if value < 0:
            raise ConfigError(f"{field_name} must not be negative (got {value}).")
    if cfg.chunk_overlap >= cfg.chunk_size:
        raise ConfigError(
            "chunk_overlap must be smaller than chunk_size "
            f"(got {cfg.chunk_overlap} >= {cfg.chunk_size})."
        )
    if cfg.ingester not in _INGESTERS:
        choices = ", ".join(sorted(_INGESTERS))
        raise ConfigError(f"Unknown ingester {cfg.ingester!r}. Choose one of: {choices}.")
    if cfg.figure_mode not in _FIGURE_MODES:
        choices = ", ".join(sorted(_FIGURE_MODES))
        raise ConfigError(
            f"Unknown figure_mode {cfg.figure_mode!r}. Choose one of: {choices}."
        )
    if cfg.figure_backend not in _FIGURE_BACKENDS:
        choices = ", ".join(sorted(_FIGURE_BACKENDS))
        raise ConfigError(
            f"Unknown figure_backend {cfg.figure_backend!r}. Choose one of: {choices}."
        )
    if not 0.0 < cfg.figure_min_area_ratio <= 1.0:
        raise ConfigError(
            "figure_min_area_ratio must be greater than 0 and at most 1 "
            f"(got {cfg.figure_min_area_ratio})."
        )
    if cfg.figure_image_scale <= 0:
        raise ConfigError(
            f"figure_image_scale must be greater than 0 (got {cfg.figure_image_scale})."
        )
    if cfg.figure_mode == "describe" and not cfg.vision_model.strip():
        raise ConfigError("vision_model must be set when figure_mode is 'describe'.")
    for field_name in _RELATIVE_DIR_FIELDS:
        value = str(getattr(cfg, field_name) or "").strip()
        path = Path(value).expanduser()
        if path.is_absolute() or path.drive or ".." in path.parts:
            raise ConfigError(
                f"{field_name} must be a relative path inside the vault (got {value!r})."
            )


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
        try:
            with cfg_file.open("rb") as fh:
                data = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Invalid TOML in {cfg_file}: {exc}") from exc
        vault_override = overrides.get("vault_path") or os.environ.get("KB_VAULT")
        if (
            vault_override
            and not os.environ.get("KB_CONFIG")
            and data.get("vault_path")
            and not _same_path(data["vault_path"], vault_override)
        ):
            print(
                "paperroach: warning: ignoring "
                f"{cfg_file} because it configures vault_path={data['vault_path']!r} "
                f"but --vault/KB_VAULT selects {str(vault_override)!r}",
                file=sys.stderr,
            )
            data = {}
        for k, v in data.items():
            if k in valid:
                merged[k] = v
            else:
                print(
                    f"paperroach: warning: unknown key '{k}' in {cfg_file} (ignored)",
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
            "vault_path to kb.toml (see kb/templates/kb.example.toml)."
        )

    coerced = {k: _coerce(k, v) for k, v in merged.items()}
    cfg = Config(**coerced)

    if not cfg.vault_path.exists():
        raise ConfigError(f"Vault path does not exist: {cfg.vault_path}")
    if not cfg.vault_path.is_dir():
        raise ConfigError(f"Vault path is not a directory: {cfg.vault_path}")
    _validate_config(cfg)
    return cfg


class ConfigError(RuntimeError):
    """Raised for user-facing configuration problems."""
