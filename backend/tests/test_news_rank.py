"""Pure-function coverage for semantic/news_rank.py — fixed vectors, a fixed
`now`, no Ollama, no wall clock (constitution I/III).
Spec: specs/036-news-semantic-search; research.md R3/R4/R5/R6.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from semantic import news_rank
from settings import settings

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)


# --- recency_decay (research.md R6) --------------------------------------

def test_recency_decay_is_one_at_age_zero():
    assert news_rank.recency_decay(NOW, NOW, 14) == pytest.approx(1.0)


def test_recency_decay_is_one_half_at_one_half_life():
    published = NOW - timedelta(days=14)
    assert news_rank.recency_decay(published, NOW, 14) == pytest.approx(0.5)


def test_recency_decay_is_one_quarter_at_two_half_lives():
    published = NOW - timedelta(days=28)
    assert news_rank.recency_decay(published, NOW, 14) == pytest.approx(0.25)


def test_recency_decay_clamps_future_dates_to_no_boost():
    published = NOW + timedelta(days=10)
    assert news_rank.recency_decay(published, NOW, 14) == pytest.approx(1.0)


def test_recency_decay_disabled_by_non_positive_half_life():
    published = NOW - timedelta(days=365)
    assert news_rank.recency_decay(published, NOW, 0) == 1.0


def test_recency_decay_tolerates_a_naive_published_at():
    published = (NOW - timedelta(days=14)).replace(tzinfo=None)
    assert news_rank.recency_decay(published, NOW, 14) == pytest.approx(0.5)


# --- cosine_rank (research.md R3) --------------------------------------

def test_cosine_rank_identical_orthogonal_opposite():
    q = np.array([1.0, 0.0, 0.0])
    matrix = np.array([
        [1.0, 0.0, 0.0],   # identical -> 1
        [0.0, 1.0, 0.0],   # orthogonal -> 0
        [-1.0, 0.0, 0.0],  # opposite -> -1
    ])
    out = news_rank.cosine_rank(q, matrix)
    assert out == pytest.approx([1.0, 0.0, -1.0])


def test_cosine_rank_empty_matrix_returns_empty():
    assert news_rank.cosine_rank(np.array([1.0, 0.0]), np.empty((0, 2))).shape == (0,)


# --- score_articles (research.md R3/R6) --------------------------------

def test_score_articles_drops_wrong_length_vectors_and_orders_by_blended_score():
    q = [1.0, 0.0, 0.0]
    rows = [
        {"title": "old but perfect", "embedding": [1.0, 0.0, 0.0],
         "published_at": NOW - timedelta(days=28)},          # cos 1.0 * 0.25 = 0.25
        {"title": "fresh and good", "embedding": [0.8, 0.6, 0.0],
         "published_at": NOW},                               # cos 0.8 * 1.0 = 0.80
        {"title": "wrong dim", "embedding": [1.0, 0.0],
         "published_at": NOW},                               # dropped
    ]
    scored = news_rank.score_articles(q, rows, NOW, 14)

    assert [row["title"] for row, _ in scored] == ["fresh and good", "old but perfect"]
    assert scored[0][1] == pytest.approx(0.80)
    assert scored[1][1] == pytest.approx(0.25)


def test_score_articles_empty_when_no_row_has_a_usable_vector():
    rows = [{"title": "x", "embedding": [1.0, 2.0], "published_at": NOW}]
    assert news_rank.score_articles([1.0, 0.0, 0.0], rows, NOW, 14) == []


# --- match_question_tags (research.md R5) -----------------------------

def _registry(*pairs):
    return [{"_id": name, "embedding": vec, "embedding_model": settings.ollama_embed_model}
            for name, vec in pairs]


def test_match_question_tags_exact_string_fast_path():
    registry = _registry(("monetary policy", [1.0, 0.0, 0.0]))
    out = news_rank.match_question_tags(["Monetary Policy"], registry, [[0.0, 1.0, 0.0]], 0.72)
    assert out == ["monetary policy"]


def test_match_question_tags_near_miss_above_threshold():
    # question "interest rates" vector is close to the stored "monetary policy"
    registry = _registry(("monetary policy", [1.0, 0.0, 0.0]))
    q_vecs = [[0.8, 0.6, 0.0]]  # cosine 0.8 >= 0.72
    assert news_rank.match_question_tags(["interest rates"], registry, q_vecs, 0.72) == ["monetary policy"]


def test_match_question_tags_near_miss_below_threshold_returns_empty():
    registry = _registry(("monetary policy", [1.0, 0.0, 0.0]))
    q_vecs = [[0.6, 0.8, 0.0]]  # cosine 0.6 < 0.72
    assert news_rank.match_question_tags(["interest rates"], registry, q_vecs, 0.72) == []


def test_match_question_tags_no_registry_or_no_vecs_returns_empty():
    assert news_rank.match_question_tags(["x"], [], [[1.0, 0.0]], 0.72) == []
    assert news_rank.match_question_tags(["x"], _registry(("a", [1.0])), [], 0.72) == []


def test_match_question_tags_skips_wrong_width_registry_rows():
    registry = _registry(("stale tag", [1.0, 0.0]))  # 2-D, question is 3-D
    assert news_rank.match_question_tags(["x"], registry, [[1.0, 0.0, 0.0]], 0.72) == []


def test_match_question_tags_unions_multiple_matches_sorted():
    registry = _registry(
        ("monetary policy", [1.0, 0.0, 0.0]),
        ("inflation", [0.0, 1.0, 0.0]),
        ("semiconductors", [0.0, 0.0, 1.0]),
    )
    q_vecs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert news_rank.match_question_tags([], registry, q_vecs, 0.72) == ["inflation", "monetary policy"]


# --- build_candidate_filter (research.md R4) --------------------------

def test_filter_ticker_reason_hard_filters_with_the_embedding_guard():
    f = news_rank.build_candidate_filter({"ticker": "NVDA"}, [], NOW, ticker_pool_size=50)
    assert f == {
        "tickers": "NVDA",
        "embedding": {"$exists": True},
        "embedding_model": settings.ollama_embed_model,
    }


def test_filter_ticker_reason_adds_tag_in_when_tags_also_matched():
    f = news_rank.build_candidate_filter({"ticker": "NVDA"}, ["export controls"], NOW,
                                         ticker_pool_size=50)
    assert f["tickers"] == "NVDA"
    assert f["tags"] == {"$in": ["export controls"]}


def test_filter_thin_ticker_pool_drops_the_embedding_guard():
    f = news_rank.build_candidate_filter({"ticker": "NEWCO"}, [], NOW, ticker_pool_size=1)
    assert f == {"tickers": "NEWCO"}


def test_filter_topic_with_matched_tags():
    f = news_rank.build_candidate_filter({"ticker": None}, ["monetary policy", "inflation"], NOW)
    assert f == {
        "tags": {"$in": ["monetary policy", "inflation"]},
        "embedding": {"$exists": True},
        "embedding_model": settings.ollama_embed_model,
    }


def test_filter_topic_no_tag_match_falls_back_to_recency_window():
    f = news_rank.build_candidate_filter({"ticker": None}, [], NOW)
    assert f["published_at"] == {"$gte": NOW - timedelta(days=settings.news_rank_fallback_days)}
    assert f["embedding"] == {"$exists": True}
