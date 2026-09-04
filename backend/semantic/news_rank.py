"""Deterministic semantic ranking for news chat questions.
Spec: specs/036-news-semantic-search; research.md R3/R4/R5/R6;
data-model.md §5; contracts/chat-news-retrieval.md §3.

Every function here except `rank_articles` is pure: fixed vectors + a fixed
`now` in, a number / list / filter-dict out, no Ollama and no wall clock
(constitution III). `rank_articles` is the thin IO shell that embeds the
question, reads Mongo, and calls the pure pieces.

`build_embed_text` is hand-copied verbatim from
agent-runner/tools/news_enrich.py (constitution V — the two services share no
package); both copies are covered by their own service's tests.
"""
from datetime import timedelta

import numpy as np
from pymongo import DESCENDING
from pymongo.database import Database

import llm
from db import NEWS_ARTICLES, NEWS_TAGS
from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

# nomic-embed-text output width. Only used as a belt-and-braces guard — the
# real reference is the live question vector's length, so a model swap that
# changes the width still works once re-enrichment catches up (research.md R8).
EMBEDDING_DIM = 768


def build_embed_text(article: dict) -> str:
    """`title` + a blank line + the first `news_embed_max_chars` of `body_text`
    (research.md R10). Deterministic head truncation. Hand-copied verbatim from
    agent-runner/tools/news_enrich.py."""
    title = (article.get("title") or "").strip()
    body = (article.get("body_text") or "")[: settings.news_embed_max_chars]
    return f"{title}\n\n{body}".rstrip()


def _valid_vec(vec, dim: int) -> bool:
    return isinstance(vec, (list, tuple, np.ndarray)) and len(vec) == dim


def cosine_rank(q_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of `q_vec` against every row of `matrix`. Both are
    assumed L2-normalized already (llm.embed guarantees it for query and stored
    vectors alike), so this is a plain matrix-vector product. Returns an empty
    array for an empty matrix."""
    q = np.asarray(q_vec, dtype=float)
    m = np.asarray(matrix, dtype=float)
    if m.size == 0:
        return np.zeros(0, dtype=float)
    return m @ q


def recency_decay(published_at, now, half_life_days: float) -> float:
    """`0.5 ** (age_days / half_life_days)` (research.md R6). Age is clamped at
    0 (a future-dated story doesn't get a >1 boost); a non-positive half-life
    disables decay (returns 1.0), which is how a caller emulates
    "pure similarity, then date-sort" (research.md R6 alternative)."""
    if published_at is None or half_life_days is None or half_life_days <= 0:
        return 1.0
    p, n = published_at, now
    if p.tzinfo is not None and n.tzinfo is None:
        n = n.replace(tzinfo=p.tzinfo)
    elif p.tzinfo is None and n.tzinfo is not None:
        p = p.replace(tzinfo=n.tzinfo)
    age_days = max((n - p).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / half_life_days)


def score_articles(q_vec, rows: list[dict], now, half_life_days: float, *,
                   min_similarity: float | None = None) -> list[tuple[dict, float]]:
    """`(row, cosine * recency_decay)` for every row whose stored vector length
    matches the question vector's, sorted by score descending. Wrong-length
    vectors are dropped before the matmul (belt-and-braces over the Mongo
    filter's `embedding_model` guard). research.md R3/R6.

    `min_similarity` (optional) drops any row whose RAW cosine — before the
    recency blend — is below the floor, so a question with no genuinely close
    article grounds nothing rather than citing the most-recent near-miss
    (spec US1 AS3)."""
    q = np.asarray(q_vec, dtype=float)
    dim = q.shape[0]
    kept = [r for r in rows if _valid_vec(r.get("embedding"), dim)]
    if not kept:
        return []
    matrix = np.array([list(r["embedding"]) for r in kept], dtype=float)
    cosines = cosine_rank(q, matrix)
    scored = []
    for row, cos in zip(kept, cosines):
        if min_similarity is not None and float(cos) < min_similarity:
            continue
        scored.append(
            (row, float(cos) * recency_decay(row.get("published_at"), now, half_life_days))
        )
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def match_question_tags(candidate_tags, registry_rows, q_tag_vecs, threshold: float) -> list[str]:
    """Question-derived tag guesses -> the set of in-use `news_tags` names they
    map to (research.md R5). A registry tag matches when its embedding's cosine
    with ANY question-tag vector is >= `threshold`, or when a `candidate_tags`
    entry equals it outright (case-insensitive fast path). Registry rows whose
    embedding width doesn't match the question vectors are skipped — that is
    how "current-model rows only" is enforced without threading the model name
    through this pure function. Returned sorted for deterministic downstream
    filters."""
    matched: set[str] = set()

    registry_names = {row["_id"] for row in registry_rows if "_id" in row}
    for raw in candidate_tags or []:
        if isinstance(raw, str) and raw.strip().lower() in registry_names:
            matched.add(raw.strip().lower())

    if q_tag_vecs is not None and len(q_tag_vecs) and registry_rows:
        q = np.asarray(q_tag_vecs, dtype=float)
        if q.ndim == 1:
            q = q[None, :]
        dim = q.shape[1]
        names, vecs = [], []
        for row in registry_rows:
            emb = row.get("embedding")
            if not _valid_vec(emb, dim):
                continue
            names.append(row["_id"])
            vecs.append(list(emb))
        if vecs:
            sims = np.array(vecs, dtype=float) @ q.T  # (R, T)
            for idx, name in enumerate(names):
                if float(sims[idx].max()) >= threshold:
                    matched.add(name)

    return sorted(matched)


def build_candidate_filter(news_search: dict, matched_tags: list[str], now, *,
                           ticker_pool_size: int | None = None) -> dict:
    """The research.md R4 table as a Mongo filter dict. `news_search` is the
    chat's `news_search` object; `matched_tags` comes from
    `match_question_tags()`; `ticker_pool_size` is the count of *enriched*
    articles for `news_search.ticker` (only consulted when a ticker is set).

    - ticker set, enriched pool healthy -> hard `{tickers: ticker}` + the
      embedding guard, plus a `tags $in` when tags also matched.
    - ticker set, enriched pool < `news_rank_min_ticker_pool` -> plain
      `{tickers: ticker}` with NO embedding guard: the thin-ticker sentinel
      (`rank_articles` sees the small pool and returns recency order without
      scoring — spec US4 fallback).
    - no ticker, tags matched -> `{tags: {$in: matched_tags}}` + guard.
    - no ticker, no tags -> recency window `{published_at: {$gte: now - N}}`
      + guard (spec FR-006).
    """
    guard = {
        "embedding": {"$exists": True},
        "embedding_model": settings.ollama_embed_model,
    }
    ticker = (news_search or {}).get("ticker")

    if ticker:
        if ticker_pool_size is not None and ticker_pool_size < settings.news_rank_min_ticker_pool:
            return {"tickers": ticker}
        candidate_filter = {"tickers": ticker, **guard}
        if matched_tags:
            candidate_filter["tags"] = {"$in": list(matched_tags)}
        return candidate_filter

    if matched_tags:
        return {"tags": {"$in": list(matched_tags)}, **guard}

    cutoff = now - timedelta(days=settings.news_rank_fallback_days)
    return {"published_at": {"$gte": cutoff}, **guard}


_CANDIDATE_PROJECTION = {
    "_id": 1, "url": 1, "title": 1, "published_at": 1, "tickers": 1, "embedding": 1,
}


def _current_model_registry(db: Database) -> list[dict]:
    return list(db[NEWS_TAGS].find(
        {"embedding_model": settings.ollama_embed_model},
        {"_id": 1, "embedding": 1, "embedding_model": 1},
    ))


def _enriched_ticker_pool(db: Database, ticker: str) -> int:
    return db[NEWS_ARTICLES].count_documents({
        "tickers": ticker,
        "embedding": {"$exists": True},
        "embedding_model": settings.ollama_embed_model,
    })


def rank_articles(db: Database, news_search: dict, *, client=None, now,
                  limit: int | None = None) -> list[dict]:
    """The `mode == "semantic"` retrieval path (contracts/chat-news-retrieval.md §3):

    1. One `llm.embed()` call over `[query_text, *candidate_tags]`.
    2. Match the question's tag guesses against the `news_tags` registry
       (current-model rows only) -> `matched_tags`.
    3. `build_candidate_filter()` -> ticker hard-filter / tag `$in` /
       recency-window fallback / thin-ticker sentinel.
    4. Read the capped, `published_at`-sorted, projected candidate set.
    5. `score_articles()` (cosine x recency-decay) — unless the thin-ticker
       sentinel fired, in which case return plain recency order for that
       ticker without scoring (spec US4 fallback).
    6. Re-read and return the top `limit` FULL documents for chat.py's
       existing answer-interpretation + citation step.

    Raises `llm.LLMError` if the embedding call fails — `chat.py` catches it
    and runs the model's generated keyword pipeline instead (FR-011)."""
    limit = settings.news_rank_top_n if limit is None else limit
    news_search = news_search or {}
    query_text = news_search.get("query_text") or ""
    candidate_tags = list(news_search.get("candidate_tags") or [])
    ticker = news_search.get("ticker")

    vectors = llm.embed([query_text, *candidate_tags], client=client)
    q_vec = vectors[0]
    q_tag_vecs = vectors[1:]

    matched_tags: list[str] = []
    if q_tag_vecs:
        matched_tags = match_question_tags(
            candidate_tags, _current_model_registry(db), q_tag_vecs,
            settings.news_tag_match_threshold,
        )

    ticker_pool_size = _enriched_ticker_pool(db, ticker) if ticker else None
    thin_ticker = (
        ticker is not None
        and ticker_pool_size is not None
        and ticker_pool_size < settings.news_rank_min_ticker_pool
    )

    candidate_filter = build_candidate_filter(
        news_search, matched_tags, now, ticker_pool_size=ticker_pool_size,
    )
    candidates = list(
        db[NEWS_ARTICLES].find(candidate_filter, _CANDIDATE_PROJECTION)
        .sort("published_at", DESCENDING)
        .limit(settings.news_rank_max_candidates)
    )

    # Structured line so tests can assert the prefilter shape and quickstart
    # §4 scenario 4 can be inspected in the worker/API log (T036 / US2).
    logger.info(
        "news_rank mode=semantic ticker=%s matched_tags=%s thin_ticker=%s "
        "filter_keys=%s candidates=%d",
        ticker, matched_tags, thin_ticker, sorted(candidate_filter), len(candidates),
    )

    if thin_ticker:
        top_ids = [row["_id"] for row in candidates[:limit]]
    else:
        scored = score_articles(
            q_vec, candidates, now, settings.news_rank_half_life_days,
            min_similarity=settings.news_rank_min_similarity,
        )
        top_ids = [row["_id"] for row, _score in scored[:limit]]

    if not top_ids:
        return []
    full = {doc["_id"]: doc for doc in db[NEWS_ARTICLES].find({"_id": {"$in": top_ids}})}
    return [full[_id] for _id in top_ids if _id in full]
