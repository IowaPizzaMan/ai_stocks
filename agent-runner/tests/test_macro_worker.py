"""macro_worker.run_macro_refresh_if_due() — staleness-driven per-sector
refresh, decoupled from ticker analysis. No network: mongomock db, fake LLM,
fake FRED fetchers. Spec: specs/020-surface-macro-ui,
specs/component-specs/agent-runner/macro_worker.md
"""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

import macro_worker
from tests.test_phase5_agents import SchemaFakeLLM
from tools.db import MACRO_ANALYSIS_CACHE, TICKER_INDEX

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def reset_throttle():
    """The sweep throttle is in-process (single agent-runner deployment) —
    reset it so tests don't leak state into each other."""
    macro_worker._last_sweep_at = None
    yield
    macro_worker._last_sweep_at = None


def make_db():
    return mongomock.MongoClient()["macro_worker_test"]


def fake_fetchers():
    return {
        "get_macro_data": lambda db=None: {"FEDFUNDS": [{"date": "2026-08-01", "value": 4.25}]},
        "get_yield_curve_status": lambda db=None: {"10y_2y_spread": 0.4, "inverted": False},
    }


def test_no_active_sectors_returns_zero_and_leaves_cache_untouched():
    db = make_db()
    client = SchemaFakeLLM()

    refreshed = macro_worker.run_macro_refresh_if_due(NOW, db=db, client=client, **fake_fetchers())

    assert refreshed == 0
    assert db[MACRO_ANALYSIS_CACHE].count_documents({}) == 0
    assert len(client.calls) == 0


def test_sector_with_no_cache_doc_gets_refreshed():
    db = make_db()
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "sector": "Technology", "status": "active"})
    client = SchemaFakeLLM()

    refreshed = macro_worker.run_macro_refresh_if_due(NOW, db=db, client=client, **fake_fetchers())

    assert refreshed == 1
    doc = db[MACRO_ANALYSIS_CACHE].find_one({"sector": "Technology"})
    assert doc is not None
    # macro_analyst.run() stamps computed_at with the actual wall clock, not
    # the injected `now` — just confirm it's a real, recent timestamp.
    computed_at = doc["computed_at"].replace(tzinfo=timezone.utc)
    assert abs((computed_at - datetime.now(timezone.utc)).total_seconds()) < 5


def test_fresh_doc_is_not_refreshed():
    db = make_db()
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "sector": "Technology", "status": "active"})
    db[MACRO_ANALYSIS_CACHE].insert_one(
        {"sector": "Technology", "result": {"cached": True},
         "computed_at": NOW - timedelta(days=1)}
    )
    client = SchemaFakeLLM()

    refreshed = macro_worker.run_macro_refresh_if_due(NOW, db=db, client=client, **fake_fetchers())

    assert refreshed == 0
    assert len(client.calls) == 0
    assert db[MACRO_ANALYSIS_CACHE].find_one({"sector": "Technology"})["result"] == {"cached": True}


def test_stale_doc_is_refreshed():
    db = make_db()
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "sector": "Technology", "status": "active"})
    db[MACRO_ANALYSIS_CACHE].insert_one(
        {"sector": "Technology", "result": {"cached": True},
         "computed_at": NOW - timedelta(days=8)}
    )
    client = SchemaFakeLLM()

    refreshed = macro_worker.run_macro_refresh_if_due(NOW, db=db, client=client, **fake_fetchers())

    assert refreshed == 1
    assert db[MACRO_ANALYSIS_CACHE].find_one({"sector": "Technology"})["result"] != {"cached": True}


def test_one_sector_failure_does_not_block_the_other():
    db = make_db()
    db[TICKER_INDEX].insert_many([
        {"ticker": "AAPL", "sector": "Technology", "status": "active"},
        {"ticker": "JPM", "sector": "Financials", "status": "active"},
    ])

    class FlakyLLM(SchemaFakeLLM):
        def chat(self, **kwargs):
            prompt = kwargs["messages"][-1]["content"]
            if "Technology" in prompt:
                raise RuntimeError("ollama unavailable")
            return super().chat(**kwargs)

    client = FlakyLLM()

    refreshed = macro_worker.run_macro_refresh_if_due(NOW, db=db, client=client, **fake_fetchers())

    assert refreshed == 1
    assert db[MACRO_ANALYSIS_CACHE].find_one({"sector": "Technology"}) is None
    assert db[MACRO_ANALYSIS_CACHE].find_one({"sector": "Financials"}) is not None


def test_second_call_within_throttle_window_is_a_noop():
    db = make_db()
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "sector": "Technology", "status": "active"})
    client = SchemaFakeLLM()

    first = macro_worker.run_macro_refresh_if_due(NOW, db=db, client=client, **fake_fetchers())
    # a second sector appears, but the throttle should skip the sweep entirely
    db[TICKER_INDEX].insert_one({"ticker": "JPM", "sector": "Financials", "status": "active"})
    second = macro_worker.run_macro_refresh_if_due(
        NOW + timedelta(minutes=5), db=db, client=client, **fake_fetchers())

    assert first == 1
    assert second == 0
    assert db[MACRO_ANALYSIS_CACHE].count_documents({}) == 1
