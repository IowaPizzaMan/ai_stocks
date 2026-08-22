"""run_portfolio_digest(db) — the work_queue admin-job handler for
job_type="portfolio_digest". Spec: specs/027-stocks-news-tab-ai-summary.
"""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

from agents import portfolio_digest as portfolio_digest_agent
from tools import admin_jobs, portfolio as portfolio_tool
from tools.db import ANALYSES, PORTFOLIO_DIGEST_CACHE


@pytest.fixture
def db():
    return mongomock.MongoClient()["admin_jobs_test"]


def analysis(ticker, conviction="medium"):
    return {
        "ticker": ticker, "signal": "neutral", "conviction": conviction,
        "summary": f"{ticker} summary.", "key_trends": [], "flags": [],
        "timestamp": datetime.now(timezone.utc), "sub_reports": {},
    }


def test_registered_in_job_handlers():
    assert admin_jobs.JOB_HANDLERS["portfolio_digest"] is portfolio_tool.run_portfolio_digest


def test_zero_analyses_succeeds_without_an_llm_call(db, monkeypatch):
    called = []
    monkeypatch.setattr(
        portfolio_digest_agent, "run", lambda stocks, client=None: called.append(stocks) or {}
    )

    count = portfolio_tool.run_portfolio_digest(db)

    assert count == 0
    assert called == []  # no LLM call made
    doc = db[PORTFOLIO_DIGEST_CACHE].find_one({})
    assert doc["stock_count"] == 0
    assert doc["total_tracked_count"] == 0
    assert doc["overview"] is None
    assert doc["highlights"] == []


def test_more_than_cap_passes_exactly_25_to_the_agent(db, monkeypatch):
    for i in range(30):
        db[ANALYSES].insert_one(analysis(f"T{i}"))

    captured = {}

    def fake_run(stocks, client=None):
        captured["stocks"] = stocks
        return {"overview": "ok", "highlights": []}

    monkeypatch.setattr(portfolio_digest_agent, "run", fake_run)

    count = portfolio_tool.run_portfolio_digest(db)

    assert count == 25
    assert len(captured["stocks"]) == 25
    doc = db[PORTFOLIO_DIGEST_CACHE].find_one({})
    assert doc["stock_count"] == 25
    assert doc["total_tracked_count"] == 30
    assert doc["capped"] is True


def test_llm_failure_writes_last_error_and_reraises_leaving_prior_success_untouched(db, monkeypatch):
    db[ANALYSES].insert_one(analysis("AAPL"))
    original_generated_at = datetime.now(timezone.utc) - timedelta(hours=3)
    db[PORTFOLIO_DIGEST_CACHE].insert_one({
        "generated_at": original_generated_at,
        "overview": "Prior good summary.",
        "highlights": [], "stock_count": 1, "total_tracked_count": 1, "capped": False,
    })
    # Read back what was actually stored (Mongo truncates to millisecond
    # precision) rather than comparing against the pre-insert Python object.
    stored_generated_at = db[PORTFOLIO_DIGEST_CACHE].find_one({})["generated_at"]

    def boom(stocks, client=None):
        raise RuntimeError("ollama: connection refused")

    monkeypatch.setattr(portfolio_digest_agent, "run", boom)

    with pytest.raises(RuntimeError):
        portfolio_tool.run_portfolio_digest(db)

    doc = db[PORTFOLIO_DIGEST_CACHE].find_one({})
    assert doc["overview"] == "Prior good summary."  # untouched
    assert doc["generated_at"] == stored_generated_at  # untouched
    assert doc["last_error"] == "ollama: connection refused"
    assert doc["last_error_at"] > stored_generated_at


def test_success_after_a_prior_failure_produces_a_newer_generated_at(db, monkeypatch):
    db[ANALYSES].insert_one(analysis("AAPL"))
    db[PORTFOLIO_DIGEST_CACHE].insert_one({
        "last_error": "old failure",
        "last_error_at": datetime.now(timezone.utc) - timedelta(minutes=5),
    })

    monkeypatch.setattr(
        portfolio_digest_agent, "run",
        lambda stocks, client=None: {"overview": "Fresh.", "highlights": []},
    )

    portfolio_tool.run_portfolio_digest(db)

    doc = db[PORTFOLIO_DIGEST_CACHE].find_one({})
    assert doc["overview"] == "Fresh."
    assert doc["generated_at"] > doc["last_error_at"]
