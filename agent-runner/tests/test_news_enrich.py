"""Unit tests for tools/news_enrich.py — pure normalization + the registry
upsert and the partial-failure enrichment path. No Ollama, no clock.
Spec: specs/036-news-semantic-search; research.md R10/R11; data-model.md §1/§2.
"""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

import llm
from tools import news_enrich
from tools.db import NEWS_TAGS

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
# Mongo (and mongomock) store naive UTC and drop tzinfo on read — compare
# registry timestamps against this.
NOW_NAIVE = NOW.replace(tzinfo=None)


@pytest.fixture
def db():
    return mongomock.MongoClient()["news_enrich_test"]


# --- normalize_tag / normalize_tags (research.md R11) ---------------------

def test_normalize_lowercases_and_trims():
    assert news_enrich.normalize_tag("  Monetary Policy  ") == "monetary policy"


def test_normalize_replaces_punctuation_with_space_and_collapses():
    assert news_enrich.normalize_tag("mergers & acquisitions") == "mergers acquisitions"
    assert news_enrich.normalize_tag("U.S.-China trade") == "u s china trade"
    assert news_enrich.normalize_tag("oil   prices!!!") == "oil prices"


def test_normalize_caps_at_four_words():
    assert news_enrich.normalize_tag("one two three four five six") == "one two three four"


def test_normalize_caps_at_forty_chars():
    out = news_enrich.normalize_tag("supercalifragilistic expialidocious extrawordy")
    assert len(out) <= news_enrich.TAG_MAX_CHARS


def test_normalize_empty_and_punctuation_only_become_empty():
    assert news_enrich.normalize_tag("") == ""
    assert news_enrich.normalize_tag("!!!") == ""
    assert news_enrich.normalize_tag(None) == ""


def test_normalize_tags_drops_empties_and_dedupes_preserving_order():
    raw = ["Monetary Policy", "monetary  policy", "", "!!!", "Semiconductors"]
    assert news_enrich.normalize_tags(raw) == ["monetary policy", "semiconductors"]


def test_normalize_tags_handles_none():
    assert news_enrich.normalize_tags(None) == []


# --- build_embed_text (research.md R10) ----------------------------------

def test_build_embed_text_joins_title_and_body_with_blank_line():
    article = {"title": "Fed holds rates", "body_text": "The Federal Reserve..."}
    assert news_enrich.build_embed_text(article) == "Fed holds rates\n\nThe Federal Reserve..."


def test_build_embed_text_truncates_body_deterministically_at_the_boundary(monkeypatch):
    monkeypatch.setattr(news_enrich.settings, "news_embed_max_chars", 10)
    article = {"title": "T", "body_text": "0123456789ABCDEFGH"}
    first = news_enrich.build_embed_text(article)
    second = news_enrich.build_embed_text(article)
    assert first == second
    assert first == "T\n\n0123456789"


def test_build_embed_text_tolerates_missing_fields():
    assert news_enrich.build_embed_text({}) == ""
    assert news_enrich.build_embed_text({"title": "only title"}) == "only title"


# --- upsert_tag_registry (data-model.md §2) ----------------------------

def test_upsert_inserts_new_tag_with_embedding_and_count_one(db, monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda tags, client=None: [[0.1, 0.2]] * len(tags))
    written = news_enrich.upsert_tag_registry(db, ["Monetary Policy"], client=None, now=NOW)

    assert written == 1
    row = db[NEWS_TAGS].find_one({"_id": "monetary policy"})
    assert row["tag"] == "monetary policy"
    assert row["count"] == 1
    assert row["embedding"] == [0.1, 0.2]
    assert row["embedding_model"] == news_enrich.settings.ollama_embed_model
    assert row["first_seen"] == NOW_NAIVE
    assert row["last_seen"] == NOW_NAIVE


def test_upsert_second_time_increments_count_and_advances_last_seen_without_re_embedding(db, monkeypatch):
    calls = []

    def fake_embed(tags, client=None):
        calls.append(list(tags))
        return [[0.0, 1.0]] * len(tags)

    monkeypatch.setattr(llm, "embed", fake_embed)
    news_enrich.upsert_tag_registry(db, ["semiconductors"], client=None, now=NOW)
    later = NOW + timedelta(days=1)
    news_enrich.upsert_tag_registry(db, ["semiconductors"], client=None, now=later)

    row = db[NEWS_TAGS].find_one({"_id": "semiconductors"})
    assert row["count"] == 2
    assert row["first_seen"] == NOW_NAIVE
    assert row["last_seen"] == later.replace(tzinfo=None)
    # embed called only for the first (new) upsert, not the second
    assert calls == [["semiconductors"]]


def test_upsert_re_embeds_a_row_whose_model_is_stale(db, monkeypatch):
    db[NEWS_TAGS].insert_one({
        "_id": "oil prices", "tag": "oil prices", "embedding": [9.9],
        "embedding_model": "old-model", "count": 5,
        "first_seen": NOW, "last_seen": NOW,
    })
    monkeypatch.setattr(llm, "embed", lambda tags, client=None: [[0.5, 0.5]] * len(tags))

    news_enrich.upsert_tag_registry(db, ["oil prices"], client=None, now=NOW + timedelta(days=2))

    row = db[NEWS_TAGS].find_one({"_id": "oil prices"})
    assert row["embedding"] == [0.5, 0.5]
    assert row["embedding_model"] == news_enrich.settings.ollama_embed_model
    assert row["count"] == 6  # still just incremented


def test_upsert_with_no_usable_tags_writes_nothing(db, monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda tags, client=None: [[1.0]] * len(tags))
    assert news_enrich.upsert_tag_registry(db, ["", "!!!"], client=None, now=NOW) == 0
    assert db[NEWS_TAGS].count_documents({}) == 0


# --- _enrich partial-failure path (data-model.md §1) -------------------

def test_enrich_returns_all_six_fields_on_success(monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda text, client=None: [[0.1, 0.2, 0.3]])
    monkeypatch.setattr(llm, "generate_json",
                        lambda **kw: {"tags": ["Monetary Policy", "rates"]})

    out = news_enrich._enrich({"title": "t", "body_text": "b"}, client=None)

    assert set(out) == {"embedding", "embedding_model", "embedding_dim",
                        "embedded_at", "tags", "tags_generated_at"}
    assert out["embedding"] == [0.1, 0.2, 0.3]
    assert out["embedding_dim"] == 3
    assert out["tags"] == ["monetary policy", "rates"]


def test_enrich_keeps_embedding_and_returns_empty_tags_when_tag_call_fails(monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda text, client=None: [[0.1, 0.2, 0.3]])

    def boom(**kw):
        raise llm.LLMError("model down")

    monkeypatch.setattr(llm, "generate_json", boom)

    out = news_enrich._enrich({"title": "t", "body_text": "b"}, client=None)

    assert out["embedding"] == [0.1, 0.2, 0.3]
    assert out["tags"] == []
    assert out["tags_generated_at"] is not None


def test_enrich_propagates_an_embedding_failure(monkeypatch):
    def boom(text, client=None):
        raise llm.LLMError("ollama unreachable")

    monkeypatch.setattr(llm, "embed", boom)
    with pytest.raises(llm.LLMError):
        news_enrich._enrich({"title": "t", "body_text": "b"}, client=None)
