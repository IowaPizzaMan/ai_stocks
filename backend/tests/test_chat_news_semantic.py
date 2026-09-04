"""End-to-end semantic-news chat: US1 topic ranking, US2 tag prefilter, US3
ticker-reason grounding, US4 recency/degradation guardrails.
Spec: specs/036-news-semantic-search; quickstart.md §4 scenario table.

No Ollama: `llm.embed` / `llm.generate_text` / `screener_query.generate_pipeline`
are faked. Article + query vectors live in a shared 8-topic space
(`TOPIC_INDEX`) so "semiconductor export controls" and "trade restrictions on
chips" land near each other without sharing a keyword (SC-002).
"""
import json
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mongomock
import pytest

import llm
from db import NEWS_ARTICLES, NEWS_TAGS, SCREENER
from semantic import chat
from settings import settings

FIXTURE = Path(__file__).parent / "fixtures" / "news_semantic_corpus.json"

TOPIC_INDEX = {"chips": 0, "monetary": 1, "oil": 2, "retail": 3,
               "ai": 4, "autos": 5, "misc": 6, "pad": 7}

TAG_WEIGHTS = {
    "monetary policy": {"monetary": 1.0},
    "interest rates": {"monetary": 0.9, "pad": 0.4359},
    "semiconductors": {"chips": 1.0},
    "export controls": {"chips": 0.9, "misc": 0.4359},
    "consumer spending": {"retail": 1.0},
    "retail": {"retail": 1.0},
    "oil prices": {"oil": 1.0},
    "energy": {"oil": 0.9, "pad": 0.4359},
    "artificial intelligence": {"ai": 1.0},
    "product launch": {"misc": 1.0},
    "dividends": {"misc": 1.0},
}


def _vec(weights: dict) -> list[float]:
    v = [0.0] * len(TOPIC_INDEX)
    for topic, w in weights.items():
        v[TOPIC_INDEX[topic]] = w
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def _query_weights(text: str) -> dict:
    t = text.lower()
    if any(k in t for k in ("crypto", "blockchain", "bitcoin")):
        return {"autos": 1.0}  # a topic no fixture article covers -> no match
    if ("nvidia" in t or "nvda" in t) and any(k in t for k in ("drop", "fell", "why", "selloff", "move")):
        return {"chips": 0.97, "misc": 0.15}
    if any(k in t for k in ("chip", "semiconductor", "export", "trade restriction")):
        return {"chips": 1.0}
    if any(k in t for k in ("rate cut", "rate-cut", "fed ", "monetary", "interest rate")):
        return {"monetary": 1.0}
    if any(k in t for k in ("consumer spending", "retail")):
        return {"retail": 1.0}
    if any(k in t for k in ("oil", "crude", "energy")):
        return {"oil": 1.0}
    if any(k in t for k in ("ai", "artificial intelligence")):
        return {"ai": 1.0}
    if "dividend" in t:
        return {"misc": 1.0}
    return {"misc": 0.5, "pad": 0.5}


def _fake_embed(texts, client=None):
    items = [texts] if isinstance(texts, str) else list(texts)
    out = []
    for s in items:
        if s in TAG_WEIGHTS:
            out.append(_vec(TAG_WEIGHTS[s]))
        else:
            out.append(_vec(_query_weights(s)))
    return out


@pytest.fixture
def db():
    # mongomock dedupes clients by host, so a fixed db name would share state
    # across tests in this module — give each test its own database.
    m = mongomock.MongoClient()[f"chat_news_semantic_{uuid.uuid4().hex}"]
    payload = json.loads(FIXTURE.read_text())
    now = datetime.now(timezone.utc)
    for art in payload["articles"]:
        published = now - timedelta(days=art["published_days_ago"])
        m[NEWS_ARTICLES].insert_one({
            "_id": art["url"],
            "url": art["url"],
            "title": art["title"],
            "body_text": art["body_text"],
            "source_type": art["source_type"],
            "publisher": art["publisher"],
            "site": None,
            "author": None,
            "body_html": None,
            "image_url": None,
            "published_at": published,
            "published_date": published.date().isoformat(),
            "tickers": art["tickers"],
            "tags": art["tags"],
            "embedding": _vec(art["topic_weights"]),
            "embedding_model": settings.ollama_embed_model,
            "embedding_dim": len(TOPIC_INDEX),
            "embedded_at": now,
            "tags_generated_at": now,
            "ingested_at": now,
        })
    seen_tags = {t for art in payload["articles"] for t in art["tags"]}
    for tag in seen_tags:
        m[NEWS_TAGS].insert_one({
            "_id": tag, "tag": tag, "embedding": _vec(TAG_WEIGHTS[tag]),
            "embedding_model": settings.ollama_embed_model, "count": 1,
            "first_seen": now, "last_seen": now,
        })
    for tk in ("NVDA", "AMD", "WMT", "XOM", "MSFT"):
        m[SCREENER].insert_one({"ticker": tk, "signals_as_of": now})
    return m


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    monkeypatch.setattr(llm, "embed", _fake_embed)
    monkeypatch.setattr(llm, "generate_text", lambda **kw: "stub answer")
    monkeypatch.setattr(chat.strategy_picks, "detect", lambda *a, **k: {"is_strategy_picks": False})


def _plan(news_search, pipeline=None):
    return {
        "collection": "news_articles",
        "pipeline": pipeline or [{"$sort": {"published_at": -1}}, {"$limit": 10}],
        "in_scope": True,
        "news_search": news_search,
    }


def _answer(db, monkeypatch, question, plan):
    monkeypatch.setattr(chat, "generate_pipeline", lambda *a, **k: plan)
    return chat._generate_answer(question, [], db, client=object())


def _cited(resp):
    return {c["url"] for c in resp["citations"]}


# --- US1: topic questions (quickstart scenarios 1-3) ---------------------

def test_reworded_topic_question_cites_the_on_topic_stories(db, monkeypatch):
    plan = _plan({"mode": "semantic", "ticker": None,
                  "query_text": "trade restrictions on chips", "candidate_tags": []})
    resp = _answer(db, monkeypatch, "any recent news about trade restrictions on chips", plan)

    cited = _cited(resp)
    assert "https://ex/chips-export-1" in cited
    assert "https://ex/nvda-explainer-1" in cited
    # a retail story that only mentions a chip plant in passing is not grounded
    assert "https://ex/retail-mentions-chip" not in cited
    assert "https://ex/oil-1" not in cited


def test_on_topic_story_outranks_an_incidental_keyword_story(db, monkeypatch):
    plan = _plan({"mode": "semantic", "ticker": None,
                  "query_text": "semiconductor export controls", "candidate_tags": []})
    resp = _answer(db, monkeypatch, "news on semiconductor export controls", plan)

    urls = [c["url"] for c in resp["citations"]]
    assert urls[0] in ("https://ex/chips-export-1", "https://ex/nvda-explainer-1", "https://ex/nvda-explainer-2")
    assert "https://ex/retail-mentions-chip" not in urls


def test_no_relevant_news_returns_no_citations(db, monkeypatch):
    plan = _plan({"mode": "semantic", "ticker": None,
                  "query_text": "cryptocurrency regulation crackdown", "candidate_tags": []})
    resp = _answer(db, monkeypatch, "any news about cryptocurrency regulation", plan)

    assert resp["citations"] == []
    assert resp["match_count"] == 0


# --- US2: tag prefilter (quickstart scenarios 4-6) ---------------------

def test_tag_mapped_question_scores_only_the_tagged_pool(db, monkeypatch, caplog):
    plan = _plan({"mode": "semantic", "ticker": None,
                  "query_text": "what did the Fed signal about rate cuts",
                  "candidate_tags": ["monetary policy"]})
    with caplog.at_level(logging.INFO):
        resp = _answer(db, monkeypatch, "what did the Fed signal about rate cuts", plan)

    assert "news_rank mode=semantic" in caplog.text
    assert "'tags'" in caplog.text and "candidates=2" in caplog.text
    assert _cited(resp) <= {"https://ex/monetary-1", "https://ex/monetary-2"}


def test_two_tag_question_scores_the_union(db, monkeypatch, caplog):
    plan = _plan({"mode": "semantic", "ticker": None,
                  "query_text": "policy and chips",
                  "candidate_tags": ["monetary policy", "semiconductors"]})
    with caplog.at_level(logging.INFO):
        _answer(db, monkeypatch, "monetary policy and semiconductors", plan)

    # 2 monetary-tagged + 5 semiconductor-tagged (incl. the 40-day-old one —
    # the tag branch has no recency window) = 7 in the scored pool
    assert "candidates=7" in caplog.text


def test_unmapped_tag_question_falls_back_to_the_recency_window(db, monkeypatch, caplog):
    plan = _plan({"mode": "semantic", "ticker": None,
                  "query_text": "oil and crude supply",
                  "candidate_tags": ["commodities supercycle"]})
    with caplog.at_level(logging.INFO):
        resp = _answer(db, monkeypatch, "anything on the commodities supercycle", plan)

    assert "'published_at'" in caplog.text  # recency-window fallback filter
    assert "https://ex/oil-1" in _cited(resp)


# --- US3: ticker-reason (quickstart scenarios 7, 8, 12) ---------------

def test_why_did_nvda_drop_is_grounded_in_the_explainers(db, monkeypatch):
    plan = _plan({"mode": "semantic", "ticker": "NVDA",
                  "query_text": "why nvidia stock fell today", "candidate_tags": []})
    resp = _answer(db, monkeypatch, "why did NVDA drop today", plan)

    urls = [c["url"] for c in resp["citations"]]
    assert set(urls[:2]) == {"https://ex/nvda-explainer-1", "https://ex/nvda-explainer-2"}
    assert "https://ex/nvda-routine-dividend" not in urls


def test_nvda_export_restriction_question_cites_only_export_stories(db, monkeypatch):
    plan = _plan({"mode": "semantic", "ticker": "NVDA",
                  "query_text": "nvidia export restrictions", "candidate_tags": []})
    resp = _answer(db, monkeypatch, "NVDA news about export restrictions", plan)

    cited = _cited(resp)
    assert cited <= {"https://ex/chips-export-1", "https://ex/chips-export-2",
                     "https://ex/nvda-explainer-1", "https://ex/nvda-explainer-2"}
    assert "https://ex/nvda-routine-dividend" not in cited
    assert "https://ex/nvda-routine-launch" not in cited


def test_thin_ticker_pool_falls_back_to_plain_recency_without_crashing(db, monkeypatch):
    # MSFT has a single enriched article (< news_rank_min_ticker_pool) -> recency
    plan = _plan({"mode": "semantic", "ticker": "MSFT",
                  "query_text": "why did microsoft move", "candidate_tags": []})
    resp = _answer(db, monkeypatch, "why did MSFT move today", plan)

    assert _cited(resp) == {"https://ex/ai-1"}


# --- US4: unchanged recency + degradation (quickstart scenarios 9, 11) ---

def test_latest_ticker_news_stays_on_the_recency_path(db, monkeypatch):
    calls = []
    monkeypatch.setattr(chat.news_rank, "rank_articles",
                        lambda *a, **k: calls.append(1) or [])
    plan = _plan({"mode": "recency", "ticker": "NVDA",
                  "query_text": "latest NVDA news", "candidate_tags": []},
                 pipeline=[{"$match": {"tickers": "NVDA"}},
                           {"$sort": {"published_at": -1}}, {"$limit": 10}])
    resp = _answer(db, monkeypatch, "latest NVDA news", plan)

    assert calls == []  # semantic ranker never invoked
    assert resp["generated_query"]["news_search"]["mode"] == "recency"
    assert resp["match_count"] > 0


def test_embedding_unavailable_degrades_with_a_note_and_no_error(db, monkeypatch):
    def boom(texts, client=None):
        raise llm.LLMError("ollama down")

    monkeypatch.setattr(llm, "embed", boom)
    plan = _plan({"mode": "semantic", "ticker": None,
                  "query_text": "trade restrictions on chips", "candidate_tags": []},
                 pipeline=[{"$sort": {"published_at": -1}}, {"$limit": 5}])
    resp = _answer(db, monkeypatch, "any news about trade restrictions on chips", plan)

    assert resp["degraded"] is False
    assert chat.SEMANTIC_UNAVAILABLE_NOTE in resp["answer"]
    assert resp["match_count"] > 0  # answered from the keyword/recency fallback


def test_latency_semantic_rank_over_a_synthetic_fill_is_fast(db, monkeypatch):
    """SC-003 / FR-014 — the candidate read + NumPy rank stays well under the
    chat budget even with a large enriched pool. Not a wall-clock assertion on
    CI hardware; a smoke that the O(n) path scales."""
    import time

    now = datetime.now(timezone.utc)
    bulk = [{
        "_id": f"syn-{i}", "url": f"https://syn/{i}", "title": f"synthetic {i}",
        "body_text": "filler", "tickers": [], "tags": ["semiconductors"],
        "published_at": now - timedelta(days=i % 60),
        "published_date": (now - timedelta(days=i % 60)).date().isoformat(),
        "embedding": _vec({"chips": 1.0, "misc": (i % 7) / 10}),
        "embedding_model": settings.ollama_embed_model, "embedding_dim": len(TOPIC_INDEX),
        "source_type": "general", "publisher": "x", "ingested_at": now,
    } for i in range(3000)]
    db[NEWS_ARTICLES].insert_many(bulk)

    plan = _plan({"mode": "semantic", "ticker": None,
                  "query_text": "semiconductor export controls", "candidate_tags": []})
    started = time.perf_counter()
    resp = _answer(db, monkeypatch, "semiconductor export controls", plan)
    elapsed = time.perf_counter() - started

    assert resp["match_count"] > 0
    assert elapsed < 5.0
