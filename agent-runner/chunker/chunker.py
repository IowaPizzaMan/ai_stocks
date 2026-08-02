"""Splits large payloads into token-safe chunks before summarization.
Spec: specs/component-specs/agent-runner/chunker.md

Deterministic (no LLM here). ~4 chars/token estimate; tiktoken not required.
"""
import json

CHARS_PER_TOKEN = 4


def chunk(data, domain: str, max_tokens: int = 2000) -> list[str]:
    if domain == "transcript":
        return _chunk_transcript(data, max_tokens)
    if domain == "financials":
        return _chunk_financials(data)
    if domain == "news":
        return _chunk_news(data)
    if domain == "price_history":
        return [_downsample_price_history(data)]
    # generic: serialize and split by size
    raw = data if isinstance(data, str) else json.dumps(data, default=str)
    size = max_tokens * CHARS_PER_TOKEN
    return [raw[i:i + size] for i in range(0, len(raw), size)] or [""]


def _chunk_transcript(data, max_tokens: int) -> list[str]:
    """Transcripts arrive as [{name, speech}, ...] segments. Pack whole speaker
    turns into chunks — never split mid-speech — so tone stays readable."""
    segments = data if isinstance(data, list) else data.get("text", [])
    limit = max_tokens * CHARS_PER_TOKEN
    chunks: list[str] = []
    current = ""
    for seg in segments:
        turn = f"{seg.get('name', '?')}: {seg.get('speech', '')}\n\n"
        if current and len(current) + len(turn) > limit:
            chunks.append(current.strip())
            current = ""
        current += turn
    if current.strip():
        chunks.append(current.strip())
    return chunks or [""]


def _chunk_financials(data: dict) -> list[str]:
    """One chunk per statement type — each is independently summarizable."""
    chunks = []
    for key, payload in (data or {}).items():
        if payload:
            chunks.append(json.dumps({key: payload}, default=str))
    return chunks or [""]


def _chunk_news(data: list, per_chunk: int = 5) -> list[str]:
    articles = data or []
    chunks = []
    for i in range(0, len(articles), per_chunk):
        chunks.append(json.dumps(articles[i:i + per_chunk], default=str))
    return chunks or [""]


def _downsample_price_history(data: dict) -> str:
    """Last 60 daily bars, all weekly, last 24 monthly — enough for narrative."""
    out = {
        "daily": (data.get("daily") or [])[-60:],
        "weekly": data.get("weekly") or [],
        "monthly": (data.get("monthly") or [])[-24:],
    }
    return json.dumps(out, default=str)
