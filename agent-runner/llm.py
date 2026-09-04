"""Thin Ollama wrapper: one structured-output chat call per agent step.

Phase 3 decision (see crew.md): agents drive the LLM directly through Ollama's
structured-output mode (format=json_schema) instead of CrewAI tool-calling —
all data fetching and skill math is deterministic Python; the model only
interprets and narrates. Retries once on invalid JSON before failing loudly.
"""
import json
import math

import ollama

from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

DEFAULT_OPTIONS = {"temperature": 0.2, "num_ctx": 8192}

# 036-news-semantic-search — keeps the small embedding model resident across a
# backfill batch (up to news_enrich_batch_per_run articles per job run) so
# each article doesn't pay a cold reload. Only used by embed().
EMBED_KEEP_ALIVE = "15m"


class LLMError(Exception):
    """The model failed to produce parseable JSON after retries."""


_client: ollama.Client | None = None


def get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=settings.ollama_url)
    return _client


def generate_json(prompt: str, schema: dict, system: str = "",
                  retries: int = 1, client=None, options: dict | None = None) -> dict:
    """One chat call constrained to `schema` (JSON Schema object). Returns the
    parsed dict. Raises LLMError if the model can't produce valid JSON."""
    client = client if client is not None else get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(retries + 1):
        response = client.chat(
            model=settings.ollama_model,
            messages=messages,
            format=schema,
            options={**DEFAULT_OPTIONS, **(options or {})},
        )
        content = response["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            last_error = exc
            logger.warning("LLM returned invalid JSON (attempt %s/%s): %s",
                           attempt + 1, retries + 1, content[:200])

    raise LLMError(f"model produced invalid JSON after {retries + 1} attempts: {last_error}")


def _l2_normalize(vec: list[float]) -> list[float]:
    """Scales `vec` to unit length so a plain dot product is cosine similarity.
    Hand-mirrored from backend/llm.py (constitution V — no shared package). A
    zero vector is returned unchanged."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return list(vec)
    return [x / norm for x in vec]


def embed(texts: str | list[str], *, client=None) -> list[list[float]]:
    """Embeds one string or a list of strings via `ollama_embed_model`,
    returning one L2-normalized vector per input (always a list of lists).
    Hand-mirrored from backend/llm.py (constitution V). Spec:
    specs/036-news-semantic-search; research.md R1/R10.

    Raises LLMError on any transport/timeout failure or an empty/misshaped
    response so the enrichment caller can fail soft (partial enrichment,
    data-model.md §1)."""
    inputs = [texts] if isinstance(texts, str) else list(texts)
    if not inputs:
        return []
    client = client if client is not None else get_client()
    try:
        response = client.embed(
            model=settings.ollama_embed_model,
            input=inputs,
            keep_alive=EMBED_KEEP_ALIVE,
        )
    except Exception as exc:
        raise LLMError(f"embedding call failed: {exc}") from exc
    vectors = response.get("embeddings") if isinstance(response, dict) else getattr(response, "embeddings", None)
    if not vectors or len(vectors) != len(inputs):
        raise LLMError(
            f"embedding call returned {len(vectors) if vectors else 0} vectors for {len(inputs)} inputs"
        )
    return [_l2_normalize(list(v)) for v in vectors]


def generate_text(prompt: str, system: str = "", client=None,
                  options: dict | None = None) -> str:
    """Plain-text chat call (no schema) — used by the chunk summarizer."""
    client = client if client is not None else get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat(
        model=settings.ollama_model,
        messages=messages,
        options={**DEFAULT_OPTIONS, **(options or {})},
    )
    return response["message"]["content"]
