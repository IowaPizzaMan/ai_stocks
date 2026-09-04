"""Thin Ollama wrapper for chat query generation + answer interpretation.
Spec: specs/031-semantic-layer-chat; contracts/chat-api.md.

Ported from agent-runner/llm.py (same hand-duplication precedent as db.py's
collection constants and price_store.py — constitution Principle V: the two
services share no Python package). Two differences from the agent-runner
original, both fixing gaps logged in KNOWN_ISSUES.md for this new call site:

* An explicit `timeout` on the client — agent-runner's `llm.py` passes none
  anywhere, so a stalled generation there just blocks a background worker.
  Here it would hang an HTTP request indefinitely without one.
* `keep_alive` on every call, so qwen3:14b stays resident between chat
  questions (research.md R2 — cold model load alone costs ~10s, which would
  blow SC-001's 10-second target on every session's first question).
"""
import json
import math

import ollama

from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

DEFAULT_OPTIONS = {"temperature": 0.2, "num_ctx": 8192}

_client: ollama.Client | None = None


class LLMError(Exception):
    """The model failed to produce parseable JSON after retries, or the
    request timed out / could not reach Ollama."""


def get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=settings.ollama_url, timeout=settings.chat_ollama_timeout_seconds)
    return _client


def generate_json(prompt: str, schema: dict, system: str = "",
                  retries: int = 1, client=None, options: dict | None = None,
                  think: bool = False) -> dict:
    """One chat call constrained to `schema` (JSON Schema object) — Ollama's
    constrained decoding guarantees the raw output parses as JSON matching
    the schema shape (research.md R10); it does not guarantee the content is
    semantically correct, which is what the golden-question test suite and
    query_guard's validation exist to catch. Raises LLMError if the model
    can't produce valid JSON after retries, or if the call times out.

    `think=False` by default: qwen3 is a reasoning model, and leaving
    thinking enabled burns a large hidden token budget before any answer
    tokens appear — research.md R2 measured this as the dominant cost in a
    cold call."""
    client = client if client is not None else get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.chat(
                model=settings.ollama_model,
                messages=messages,
                format=schema,
                think=think,
                keep_alive=settings.chat_ollama_keep_alive,
                options={**DEFAULT_OPTIONS, **(options or {})},
            )
        except Exception as exc:  # connection error, timeout, etc.
            last_error = exc
            logger.warning("Ollama call failed (attempt %s/%s): %s",
                           attempt + 1, retries + 1, exc)
            continue
        content = response["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            last_error = exc
            logger.warning("LLM returned invalid JSON (attempt %s/%s): %s",
                           attempt + 1, retries + 1, content[:200])

    raise LLMError(f"model call failed after {retries + 1} attempts: {last_error}")


def prewarm() -> None:
    """Loads the chat model into Ollama and keeps it resident for
    chat_ollama_keep_alive, so the first real question isn't the one that
    pays the ~10s cold model-load cost measured in research.md R2 (that
    alone would blow SC-001's 10-second target on every session's first
    question). Best-effort — a failure here (e.g. Ollama not up yet at
    backend startup) must never block or crash startup; the model simply
    loads lazily on the first real call instead."""
    try:
        get_client().chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": "ready"}],
            think=False,
            keep_alive=settings.chat_ollama_keep_alive,
            options={**DEFAULT_OPTIONS, "num_predict": 1},
        )
        logger.info("chat model %s pre-warmed", settings.ollama_model)
    except Exception as exc:
        logger.warning("chat model pre-warm failed (will load on first question): %s", exc)


def _l2_normalize(vec: list[float]) -> list[float]:
    """Scales `vec` to unit length so a plain dot product is cosine similarity
    (semantic/news_rank.py assumes every stored and query vector is already
    normalized). A zero vector is returned unchanged — it can't be normalized,
    and news_rank drops zero/degenerate rows before the matmul anyway."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return list(vec)
    return [x / norm for x in vec]


def embed(texts: str | list[str], *, client=None) -> list[list[float]]:
    """Embeds one string or a list of strings via `ollama_embed_model`,
    returning one L2-normalized vector per input (always a list of lists, even
    for a single string). Spec: specs/036-news-semantic-search; research.md R1;
    contracts/chat-news-retrieval.md §4.

    Raises LLMError on any transport/timeout failure or an empty/misshaped
    response, so callers (news_rank.rank_articles → chat.py) get the same
    error type as the chat calls and can fall back to the keyword pipeline
    (FR-011). Passes `keep_alive` so the embedding model stays resident
    between questions, same rationale as generate_json()."""
    inputs = [texts] if isinstance(texts, str) else list(texts)
    if not inputs:
        return []
    client = client if client is not None else get_client()
    try:
        response = client.embed(
            model=settings.ollama_embed_model,
            input=inputs,
            keep_alive=settings.chat_ollama_keep_alive,
        )
    except Exception as exc:  # connection error, timeout, model missing, etc.
        raise LLMError(f"embedding call failed: {exc}") from exc
    vectors = response.get("embeddings") if isinstance(response, dict) else getattr(response, "embeddings", None)
    if not vectors or len(vectors) != len(inputs):
        raise LLMError(
            f"embedding call returned {len(vectors) if vectors else 0} vectors for {len(inputs)} inputs"
        )
    return [_l2_normalize(list(v)) for v in vectors]


def generate_text(prompt: str, system: str = "", client=None,
                  options: dict | None = None, think: bool = False) -> str:
    """Plain-text chat call (no schema) — used for chat's answer-interpretation
    step. Raises LLMError on a connection failure or timeout so callers get a
    uniform error type rather than a raw ollama/httpx exception."""
    client = client if client is not None else get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        response = client.chat(
            model=settings.ollama_model,
            messages=messages,
            think=think,
            keep_alive=settings.chat_ollama_keep_alive,
            options={**DEFAULT_OPTIONS, **(options or {})},
        )
    except Exception as exc:
        raise LLMError(f"model call failed: {exc}") from exc
    return response["message"]["content"]
