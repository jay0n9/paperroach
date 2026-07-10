"""Thin, defensive wrapper around the Ollama Python client.

Responsibilities
----------------
* PASS A — JSON-mode generation with Qwen3 *thinking disabled*.
* PASS A→B swap — explicitly unload a model (``keep_alive = 0``) so the 7GB
  LLM and the 1.2GB embedder never need to co-reside on an 8GB GPU.
* PASS B — batched, L2-normalised embeddings (cosine-ready).

The Ollama Python responses changed shape across versions (dict-like vs.
pydantic objects, ``embed`` vs. ``embeddings``); every access goes through a
small compatibility shim so we work on old and new clients alike.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.request

try:
    import ollama
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "The 'ollama' Python package is required. Install it with:\n"
        "    pip install ollama\n"
        "and make sure the Ollama server is running (https://ollama.com)."
    ) from exc

from kb.config import Config

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _content(resp) -> str:
    """Extract assistant text from a chat response (dict or pydantic)."""
    msg = getattr(resp, "message", None)
    if msg is not None:
        return getattr(msg, "content", "") or ""
    try:
        return resp["message"]["content"] or ""
    except (TypeError, KeyError):
        return ""


def _embeddings(resp) -> list[list[float]]:
    """Extract a list of vectors from an embed response (dict or pydantic)."""
    emb = getattr(resp, "embeddings", None)
    if emb is None:
        try:
            emb = resp["embeddings"]
        except (TypeError, KeyError):
            emb = None
    if emb is None:  # very old single-embedding shape
        single = getattr(resp, "embedding", None)
        if single is None:
            try:
                single = resp["embedding"]
            except (TypeError, KeyError):
                single = None
        emb = [single] if single is not None else []
    return [list(v) for v in emb]


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return list(vec)
    return [x / norm for x in vec]


def _strip_think(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


class OllamaError(RuntimeError):
    pass


# Exceptions worth one retry: connection blips and server-side (5xx) errors.
# Client-side errors (bad request, unknown model) fail fast.
def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status >= 500
    name = type(exc).__name__
    return name in {"ConnectError", "ReadTimeout", "ConnectTimeout", "ReadError"}


class OllamaClient:
    # A generation on an 8GB GPU can legitimately take minutes, but "forever"
    # always means a wedged server — bound every generative call.
    REQUEST_TIMEOUT = 600  # seconds

    def __init__(self, config: Config):
        self.config = config
        self.client = ollama.Client(host=config.ollama_host, timeout=self.REQUEST_TIMEOUT)

    def ping(self) -> None:
        """Fail fast (before any expensive work) if the server is unreachable."""
        url = self.config.ollama_host.rstrip("/") + "/api/version"
        try:
            urllib.request.urlopen(url, timeout=10).read()
        except Exception as exc:
            raise OllamaError(
                f"Ollama server is not reachable at {self.config.ollama_host} "
                f"({exc}). Start it with 'ollama serve' and retry."
            ) from exc

    # ── PASS A : LLM ────────────────────────────────────────────────
    def _chat(self, messages, *, fmt=None, temperature: float) -> str:
        cfg = self.config
        # Fixed seed + low temperature → reproducible extraction, so re-building
        # a paper yields the SAME concept names (no duplicate notes).
        options = {
            "num_ctx": cfg.llm_num_ctx,
            "temperature": temperature,
            "seed": cfg.llm_seed,
        }
        kwargs = dict(
            model=cfg.llm_model,
            messages=messages,
            options=options,
            keep_alive=cfg.keep_alive,
        )
        if fmt is not None:
            kwargs["format"] = fmt
        # Disable Qwen3 "thinking" for speed and lower VRAM. Newer clients
        # accept think=...; older clients raise TypeError and older *servers*
        # reject the field with a ResponseError — both fall back to /no_think.
        if not cfg.llm_think:
            try:
                return _strip_think(self._chat_retry(think=False, **kwargs))
            except TypeError:
                pass
            except ollama.ResponseError as exc:
                if "think" not in str(exc).lower():
                    raise
            msgs = [dict(m) for m in messages]
            msgs[0]["content"] = msgs[0]["content"] + "\n/no_think"
            kwargs["messages"] = msgs
        return _strip_think(self._chat_retry(**kwargs))

    def _chat_retry(self, **kwargs) -> str:
        """One retry with backoff on transient (connection / 5xx) errors."""
        try:
            return self._chat_stream(**kwargs)
        except Exception as exc:
            if not _is_transient(exc):
                raise
            print(f"  ! transient Ollama error ({exc}); retrying …", file=sys.stderr)
            time.sleep(5)
            return self._chat_stream(**kwargs)

    def _chat_stream(self, **kwargs) -> str:
        """Stream the response and join the chunks.

        A long generation (big JSON vocabularies, wiki articles) can exceed
        any fixed read timeout when fetched as ONE response; streamed, the
        timeout applies between chunks, so slow-but-alive generations always
        finish while a wedged server is still detected within REQUEST_TIMEOUT.
        """
        parts: list[str] = []
        for chunk in self.client.chat(stream=True, **kwargs):
            parts.append(_content(chunk))
        return "".join(parts)

    def generate_json(self, system: str, user: str) -> dict:
        """Run the LLM in JSON mode and return a parsed object.

        A malformed/truncated response gets one repair attempt before the
        error propagates (an 8B model occasionally emits broken JSON even
        with format="json").
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        raw = self._chat(messages, fmt="json", temperature=0.0)
        try:
            return _loads_lenient(raw)
        except OllamaError:
            repair = messages + [
                {"role": "assistant", "content": raw[:4000]},
                {
                    "role": "user",
                    "content": "Your previous output was not valid JSON. "
                    "Return ONLY the complete, valid JSON object now.",
                },
            ]
            raw = self._chat(repair, fmt="json", temperature=0.0)
            return _loads_lenient(raw)

    def generate_vision_json(self, system: str, user: str, image_path) -> dict:
        """Run one image-grounded, JSON-mode vision request.

        The vision model is deliberately separate from ``llm_model``. The
        pipeline loads it once for every figure batch, then evicts it before
        the text LLM and embedder run on an 8 GB GPU.
        """
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": user,
                "images": [str(image_path)],
            },
        ]
        kwargs = {
            "model": self.config.vision_model,
            "messages": messages,
            "format": "json",
            "options": {
                "num_ctx": self.config.llm_num_ctx,
                "temperature": 0.0,
                "seed": self.config.llm_seed,
            },
            "keep_alive": self.config.keep_alive,
        }
        raw = self._chat_retry(**kwargs)
        try:
            return _loads_lenient(raw)
        except OllamaError:
            repair = messages + [
                {"role": "assistant", "content": raw[:4000]},
                {
                    "role": "user",
                    "content": "Return only the complete JSON object requested above.",
                },
            ]
            kwargs["messages"] = repair
            return _loads_lenient(self._chat_retry(**kwargs))

    def generate_text(self, system: str, user: str, *, temperature: float = 0.3) -> str:
        """Free-form generation (used by `ask`)."""
        return self._chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            fmt=None,
            temperature=temperature,
        )

    # ── PASS B : embeddings ─────────────────────────────────────────
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return L2-normalised embeddings for ``texts`` (batched)."""
        if not texts:
            return []
        cfg = self.config
        try:
            try:
                resp = self.client.embed(
                    model=cfg.embed_model, input=texts, keep_alive=cfg.keep_alive
                )
            except Exception as exc:
                if not _is_transient(exc):
                    raise
                print(f"  ! transient Ollama error ({exc}); retrying …", file=sys.stderr)
                time.sleep(5)
                resp = self.client.embed(
                    model=cfg.embed_model, input=texts, keep_alive=cfg.keep_alive
                )
            vecs = _embeddings(resp)
        except AttributeError:
            # Ancient client: only per-prompt `embeddings`.
            vecs = []
            for t in texts:
                r = self.client.embeddings(model=cfg.embed_model, prompt=t)
                vecs.extend(_embeddings(r))
        if len(vecs) != len(texts):
            raise OllamaError(
                f"Embedder returned {len(vecs)} vectors for {len(texts)} inputs."
            )
        return [_normalize(v) for v in vecs]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    # ── PASS A→B swap ───────────────────────────────────────────────
    def unload(self, model: str) -> None:
        """Evict ``model`` from VRAM immediately (keep_alive = 0).

        Uses a raw POST to /api/generate which works for both generative and
        embedding models, regardless of client version. On an 8GB GPU this is
        the *correctness* mechanism that prevents the LLM and embedder from
        co-residing, so a failure is surfaced loudly rather than swallowed.
        """
        url = self.config.ollama_host.rstrip("/") + "/api/generate"
        payload = json.dumps({"model": model, "keep_alive": 0}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=60).read()
        except Exception as exc:
            print(
                f"  ! WARNING: could not unload '{model}' from VRAM ({exc}). "
                f"It may stay resident and co-reside with the next model on an "
                f"8GB GPU (slow CPU offload). Is Ollama running at "
                f"{self.config.ollama_host}?",
                file=sys.stderr,
                flush=True,
            )
            return
        if self._is_loaded(model):
            print(
                f"  ! WARNING: '{model}' is still resident after an unload "
                f"request; the next model may co-reside on VRAM. Consider "
                f"setting OLLAMA_MAX_LOADED_MODELS=1 on the Ollama server.",
                file=sys.stderr,
                flush=True,
            )

    def _is_loaded(self, model: str) -> bool:
        """Best-effort check of /api/ps for whether ``model`` is resident."""
        url = self.config.ollama_host.rstrip("/") + "/api/ps"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return False
        base = model.split(":")[0]
        for m in data.get("models", []):
            name = m.get("name") or m.get("model") or ""
            if name == model or name.split(":")[0] == base:
                return True
        return False

    def unload_llm(self) -> None:
        self.unload(self.config.llm_model)

    def unload_embed(self) -> None:
        self.unload(self.config.embed_model)

    def unload_vision(self) -> None:
        self.unload(self.config.vision_model)


def _loads_lenient(raw: str) -> dict:
    """Parse JSON, tolerating stray prose around the object."""
    raw = raw.strip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise OllamaError(f"LLM did not return JSON:\n{raw[:500]}")
        try:
            obj = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise OllamaError(
                f"LLM returned malformed/truncated JSON ({exc}):\n{raw[:500]}"
            ) from exc
    if not isinstance(obj, dict):
        raise OllamaError(f"Expected a JSON object, got {type(obj).__name__}.")
    return obj
