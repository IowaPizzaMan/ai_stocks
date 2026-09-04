"""Per-article enrichment for semantic news search: one embedding + a short
set of free-form topic tags, plus the `news_tags` usage registry.
Spec: specs/036-news-semantic-search; research.md R7/R10/R11; data-model.md §1/§2.

Split pure-core / IO-shell the same way news_pull.py already splits `_normalize`
from its fetch loop:

* `build_embed_text`, `normalize_tag`, `normalize_tags` — pure, exhaustively
  unit-tested without Ollama (constitution I/III).
* `_enrich`, `upsert_tag_registry` — the IO shell: they call `llm.embed()` /
  `llm.generate_json()` and write Mongo. `news_pull.py` calls both.

`build_embed_text` is hand-copied into backend/semantic/news_rank.py
(constitution V — the two services share no package); both copies are covered
by their own service's tests.
"""
import re
from datetime import datetime, timezone

import llm
from logging_config import get_logger
from settings import settings
from tools.db import NEWS_TAGS

logger = get_logger(__name__)

TAG_MIN = 3
TAG_MAX = 6  # advisory, enforced only in the prompt — normalize keeps whatever the model returns
TAG_MAX_WORDS = 4
TAG_MAX_CHARS = 40

_PUNCT_RE = re.compile(r"[^a-z0-9\s]+")
_WS_RE = re.compile(r"\s+")

# research.md R11 — steer the model toward broad, *recurring* topics so the
# news_tags registry doesn't fill with headline-specific singletons (the main
# failure mode of open tagging). Company-name topics are redundant with the
# existing `tickers` array.
TAG_SYSTEM_PROMPT = (
    "You label a news story with broad, reusable topic tags — the kind a reader "
    "would browse a news site by. Return 3 to 6 tags.\n"
    "Good tags: \"monetary policy\", \"semiconductors\", \"mergers and "
    "acquisitions\", \"oil prices\", \"artificial intelligence\", \"labor market\".\n"
    "Do NOT use: a single company's name, a ticker symbol, a person's name, a "
    "date, or a phrase copied from the headline. Prefer a general theme over a "
    "specific event.\n"
    'Reply with JSON: {"tags": ["...", "..."]}.'
)

# Ollama constrained-decoding schema for the tag call. The array-of-strings
# shape is guaranteed; breadth/quality is the prompt's job and the golden set's.
TAG_SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
    "required": ["tags"],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_embed_text(article: dict) -> str:
    """`title` + a blank line + the first `news_embed_max_chars` of `body_text`
    (research.md R10). Deterministic head truncation — the same article always
    yields the same string (spec Edge Case), which is what makes a recorded
    embedding fixture stable. Hand-copied verbatim into
    backend/semantic/news_rank.py."""
    title = (article.get("title") or "").strip()
    body = (article.get("body_text") or "")[: settings.news_embed_max_chars]
    return f"{title}\n\n{body}".rstrip()


def normalize_tag(raw: str) -> str:
    """One tag -> its canonical form: lowercase, punctuation replaced with
    spaces, whitespace collapsed to single spaces, trimmed, capped at
    TAG_MAX_WORDS words and TAG_MAX_CHARS characters. Returns "" for anything
    that normalizes to empty (research.md R11; data-model.md §1)."""
    if not isinstance(raw, str):
        return ""
    text = _PUNCT_RE.sub(" ", raw.lower())
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return ""
    text = " ".join(text.split(" ")[:TAG_MAX_WORDS])
    if len(text) > TAG_MAX_CHARS:
        text = text[:TAG_MAX_CHARS].rstrip()
    return text


def normalize_tags(raw_tags) -> list[str]:
    """Normalizes each entry, drops empties, and dedupes while preserving first
    -seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_tags or []:
        tag = normalize_tag(raw)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def _tag_prompt(article: dict) -> str:
    title = (article.get("title") or "").strip()
    body = (article.get("body_text") or "")[: settings.news_embed_max_chars]
    return f"Headline: {title}\n\nStory:\n{body}"


def _enrich(article: dict, *, client) -> dict:
    """Produces the six enrichment fields for one article (data-model.md §1):
    `embedding`, `embedding_model`, `embedding_dim`, `embedded_at`, `tags`,
    `tags_generated_at`.

    One `llm.embed()` call and one `llm.generate_json()` tag call. If the tag
    call fails, returns a *partial*: the embedding is kept, `tags` is `[]`, and
    `tags_generated_at` is still stamped (the backfill retries a partial while
    `tags == []`). An embedding failure is not caught here — it propagates as
    `llm.LLMError` so the caller skips the article this run."""
    now = _utcnow()
    vector = llm.embed(build_embed_text(article), client=client)[0]
    result = {
        "embedding": vector,
        "embedding_model": settings.ollama_embed_model,
        "embedding_dim": len(vector),
        "embedded_at": now,
        "tags": [],
        "tags_generated_at": now,
    }
    try:
        raw = llm.generate_json(
            prompt=_tag_prompt(article),
            schema=TAG_SCHEMA,
            system=TAG_SYSTEM_PROMPT,
            client=client,
            options={"temperature": 0},
        )
    except llm.LLMError as exc:
        logger.warning("tag generation failed for %s (embedding kept): %s",
                       article.get("url"), exc)
        return result
    result["tags"] = normalize_tags(raw.get("tags"))
    result["tags_generated_at"] = _utcnow()
    return result


def upsert_tag_registry(db, tags, *, client, now) -> int:
    """Upserts one `news_tags` row per normalized tag (data-model.md §2):
    `$setOnInsert` the natural-key `tag` + `first_seen`, `$set` `last_seen`,
    `$inc` `count` by 1. A brand-new tag — or an existing row whose
    `embedding_model` is stale — gets its `embedding` (re)computed with one
    batched `llm.embed()` call. Returns the number of tags written."""
    normalized = normalize_tags(tags)
    if not normalized:
        return 0
    current_model = settings.ollama_embed_model

    stored_model = {
        row["_id"]: row.get("embedding_model")
        for row in db[NEWS_TAGS].find({"_id": {"$in": normalized}}, {"embedding_model": 1})
    }
    needs_vector = [t for t in normalized if stored_model.get(t) != current_model]
    vectors: dict[str, list[float]] = {}
    if needs_vector:
        vectors = dict(zip(needs_vector, llm.embed(needs_vector, client=client)))

    for tag in normalized:
        set_fields: dict = {"last_seen": now}
        if tag in vectors:
            set_fields["embedding"] = vectors[tag]
            set_fields["embedding_model"] = current_model
        db[NEWS_TAGS].update_one(
            {"_id": tag},
            {
                "$set": set_fields,
                "$setOnInsert": {"tag": tag, "first_seen": now},
                "$inc": {"count": 1},
            },
            upsert=True,
        )
    return len(normalized)
