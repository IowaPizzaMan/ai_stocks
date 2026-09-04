"""backend/semantic/screener_query.py — shared question-to-pipeline generation.
Spec: specs/033-strategy-picks-filters (extraction); specs/035-chat-and-news-upgrade
US1 (FR-010, FR-011) — the system prompt must actually teach the model how to
build a $group aggregation, not just $match/$sort/$limit (research.md R4).
"""
from unittest.mock import patch

from semantic import screener_query


def test_system_prompt_contains_a_group_example_with_an_accumulator():
    prompt = screener_query.build_system_prompt()
    assert "$group" in prompt
    assert any(acc in prompt for acc in ("$avg", "$sum", "$count"))


def test_system_prompt_still_lists_every_screener_field():
    prompt = screener_query.build_system_prompt()
    for field in screener_query.SCREENER_SCHEMA["fields"]:
        assert field["name"] in prompt


def test_generate_pipeline_calls_llm_generate_json_with_the_query_schema():
    with patch("semantic.screener_query.llm.generate_json") as mock_generate:
        mock_generate.return_value = {"collection": "screener", "pipeline": [], "in_scope": True}
        result = screener_query.generate_pipeline("some prompt text")

    mock_generate.assert_called_once()
    _, kwargs = mock_generate.call_args
    assert kwargs["schema"] == screener_query.QUERY_SCHEMA
    assert kwargs["options"] == {"temperature": 0}
    assert result == {"collection": "screener", "pipeline": [], "in_scope": True}


# --- 036 news_search object (contracts/chat-news-retrieval.md §1-2) --------

def test_query_schema_has_an_optional_news_search_object_with_the_four_fields():
    props = screener_query.QUERY_SCHEMA["properties"]
    assert "news_search" not in screener_query.QUERY_SCHEMA["required"]
    ns = props["news_search"]
    assert ns["type"] == "object"
    assert set(ns["properties"]) == {"mode", "ticker", "query_text", "candidate_tags"}
    assert ns["properties"]["mode"]["enum"] == ["recency", "semantic"]


def test_system_prompt_teaches_semantic_vs_recency_news_modes():
    prompt = screener_query.build_system_prompt()
    assert "news_search" in prompt
    assert '"mode": "semantic"' in prompt or "mode \"semantic\"" in prompt
    assert "candidate_tags" in prompt


def test_system_prompt_routes_a_ticker_why_question_to_ticker_reason_mode():
    prompt = screener_query.build_system_prompt()
    # a "why did <ticker> move" example that keeps mode semantic with the
    # ticker set (US3 / FR-010a) — not plain recency
    assert "why did NVDA drop today" in prompt
    assert "ticker-reason mode, NOT plain recency" in prompt


def test_coerce_news_search_defaults_a_missing_object_to_recency():
    out = screener_query.coerce_news_search(None, question="latest NVDA news")
    assert out == {"mode": "recency", "ticker": None,
                   "query_text": "latest NVDA news", "candidate_tags": []}


def test_coerce_news_search_keeps_a_known_ticker_and_drops_an_unknown_one():
    known = {"NVDA"}
    assert screener_query.coerce_news_search(
        {"mode": "semantic", "ticker": "nvda", "query_text": "why nvda fell", "candidate_tags": []},
        question="q", known_tickers=known,
    )["ticker"] == "NVDA"
    assert screener_query.coerce_news_search(
        {"mode": "semantic", "ticker": "ZZZZ", "query_text": "q", "candidate_tags": []},
        question="q", known_tickers=known,
    )["ticker"] is None


def test_coerce_news_search_falls_back_to_the_question_when_query_text_is_empty():
    out = screener_query.coerce_news_search(
        {"mode": "semantic", "ticker": None, "query_text": "  ", "candidate_tags": []},
        question="what about rate cuts",
    )
    assert out["query_text"] == "what about rate cuts"


def test_coerce_news_search_trims_over_long_query_text_and_caps_tags_at_four():
    out = screener_query.coerce_news_search(
        {"mode": "semantic", "ticker": None, "query_text": "x" * 900,
         "candidate_tags": ["a", "b", "c", "d", "e", "f"]},
        question="q",
    )
    assert len(out["query_text"]) == screener_query.NEWS_QUERY_TEXT_MAX
    assert out["candidate_tags"] == ["a", "b", "c", "d"]


def test_coerce_news_search_downgrades_an_unknown_mode_to_recency():
    out = screener_query.coerce_news_search(
        {"mode": "vibes", "ticker": None, "query_text": "q", "candidate_tags": []},
        question="q",
    )
    assert out["mode"] == "recency"
