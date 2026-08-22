"""Cross-stock AI summary — gather/condense/rank/cap (tools/portfolio.py) and
the LLM synthesis (agents/portfolio_digest.py). Spec: specs/027.
"""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

from agents import portfolio_digest as portfolio_digest_agent
from tools import portfolio as portfolio_tool
from tools.db import ANALYSES


@pytest.fixture
def db():
    return mongomock.MongoClient()["portfolio_digest_test"]


def analysis(ticker, conviction="medium", signal="neutral", timestamp=None, stance=None):
    return {
        "ticker": ticker,
        "signal": signal,
        "conviction": conviction,
        "summary": f"{ticker} summary.",
        "key_trends": [f"{ticker} trend"],
        "flags": [],
        "timestamp": timestamp or datetime.now(timezone.utc),
        "sub_reports": {"news": {"stance": stance}},
    }


# --- tools/portfolio.py: gather/condense/rank/cap -----------------------------


def test_zero_analyses_returns_empty_list(db):
    condensed, total, capped = portfolio_tool.gather_and_rank(db)
    assert condensed == []
    assert total == 0
    assert capped is False


def test_fewer_than_cap_returns_all_uncapped(db):
    for i in range(5):
        db[ANALYSES].insert_one(analysis(f"T{i}"))

    condensed, total, capped = portfolio_tool.gather_and_rank(db, cap=25)

    assert len(condensed) == 5
    assert total == 5
    assert capped is False


def test_more_than_cap_is_truncated_and_flagged(db):
    for i in range(30):
        db[ANALYSES].insert_one(analysis(f"T{i}"))

    condensed, total, capped = portfolio_tool.gather_and_rank(db, cap=25)

    assert len(condensed) == 25
    assert total == 30
    assert capped is True


def test_selection_prioritizes_highest_conviction_first(db):
    now = datetime.now(timezone.utc)
    db[ANALYSES].insert_one(analysis("LOW1", conviction="low", timestamp=now))
    db[ANALYSES].insert_one(analysis("HIGH1", conviction="high", timestamp=now - timedelta(days=5)))
    db[ANALYSES].insert_one(analysis("MED1", conviction="medium", timestamp=now))

    condensed, _, _ = portfolio_tool.gather_and_rank(db, cap=2)

    tickers = [c["ticker"] for c in condensed]
    assert tickers == ["HIGH1", "MED1"]  # LOW1 excluded despite being newest


def test_ties_broken_by_most_recently_analyzed(db):
    now = datetime.now(timezone.utc)
    db[ANALYSES].insert_one(analysis("OLDER", conviction="high", timestamp=now - timedelta(days=10)))
    db[ANALYSES].insert_one(analysis("NEWER", conviction="high", timestamp=now))

    condensed, _, _ = portfolio_tool.gather_and_rank(db, cap=25)

    assert [c["ticker"] for c in condensed] == ["NEWER", "OLDER"]


def test_condensed_entry_shape(db):
    db[ANALYSES].insert_one(analysis(
        "AAPL", conviction="high", signal="bullish",
        stance={"direction": "bullish", "reasoning": "Strong quarter."},
    ))

    condensed, _, _ = portfolio_tool.gather_and_rank(db)

    entry = condensed[0]
    assert entry["ticker"] == "AAPL"
    assert entry["signal"] == "bullish"
    assert entry["conviction"] == "high"
    assert entry["summary"] == "AAPL summary."
    assert entry["key_trends"] == ["AAPL trend"]
    assert entry["flags"] == []
    assert entry["news_stance"] == {"direction": "bullish", "reasoning": "Strong quarter."}


def test_missing_news_stance_condenses_to_none(db):
    doc = analysis("NOSTANCE")
    doc["sub_reports"] = {}
    db[ANALYSES].insert_one(doc)

    condensed, _, _ = portfolio_tool.gather_and_rank(db)

    assert condensed[0]["news_stance"] is None


# --- agents/portfolio_digest.py: schema-validated synthesis --------------------


def test_run_prompts_with_every_condensed_stock_and_returns_the_schema(monkeypatch):
    captured = {}

    def fake_generate_json(prompt, schema, system="", client=None, **kwargs):
        captured["prompt"] = prompt
        captured["schema"] = schema
        return {
            "overview": "Momentum skews bullish.",
            "highlights": [
                {"ticker": "AAPL", "signal": "bullish", "conviction": "high", "note": "Strong."},
            ],
        }

    monkeypatch.setattr(portfolio_digest_agent, "generate_json", fake_generate_json)

    stocks = [
        {"ticker": "AAPL", "signal": "bullish", "conviction": "high", "summary": "s",
         "key_trends": [], "flags": [], "news_stance": None},
        {"ticker": "CAH", "signal": "bearish", "conviction": "medium", "summary": "s2",
         "key_trends": [], "flags": [], "news_stance": None},
    ]

    result = portfolio_digest_agent.run(stocks)

    assert "AAPL" in captured["prompt"]
    assert "CAH" in captured["prompt"]
    assert result["overview"] == "Momentum skews bullish."
    assert result["highlights"][0]["ticker"] == "AAPL"
    assert captured["schema"]["required"] == ["overview", "highlights"]
