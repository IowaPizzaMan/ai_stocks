"""get_superinvestor_activity's 7-day shared-scrape cache — Playwright/Ollama
faked, no network."""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

import tools.superinvestor as superinvestor
from tools.db import DATAROMA_META, SUPERINVESTOR_MOVES_CACHE


def make_db():
    return mongomock.MongoClient()["superinvestor_test"]


ALL_MOVES = [
    {"fund": "Berkshire", "action": "add", "ticker": "AAPL", "detail": "+2%"},
    {"fund": "Pershing", "action": "trim", "ticker": "MSFT", "detail": "-1%"},
]


@pytest.fixture
def fetch_and_extract_spy(monkeypatch):
    calls = {"fetch": 0, "extract": 0}

    def fake_fetch(url):
        calls["fetch"] += 1
        return "page text"

    def fake_extract(page_text, ticker, client=None):
        calls["extract"] += 1
        moves = ALL_MOVES
        if ticker:
            moves = [m for m in moves if m["ticker"] == ticker]
        return moves

    monkeypatch.setattr(superinvestor, "_fetch_page_text", fake_fetch)
    monkeypatch.setattr(superinvestor, "_extract_moves", fake_extract)
    return calls


def test_first_call_scrapes_and_caches_all_moves(fetch_and_extract_spy):
    db = make_db()
    result = superinvestor.get_superinvestor_activity("AAPL", db=db)

    assert fetch_and_extract_spy["fetch"] == 1
    assert result["available"] is True
    assert result["moves"] == [ALL_MOVES[0]]
    cached = db[SUPERINVESTOR_MOVES_CACHE].find_one({})
    assert cached["moves"] == ALL_MOVES  # cache holds everyone, not just AAPL
    assert db[DATAROMA_META].find_one({"key": "last_pull"}) is not None


def test_second_ticker_within_window_reuses_cache_no_new_scrape(fetch_and_extract_spy):
    db = make_db()
    superinvestor.get_superinvestor_activity("AAPL", db=db)
    result = superinvestor.get_superinvestor_activity("MSFT", db=db)

    assert fetch_and_extract_spy["fetch"] == 1  # not called again
    assert result["available"] is True
    assert result["moves"] == [ALL_MOVES[1]]


def test_ticker_with_no_moves_in_cache_returns_empty(fetch_and_extract_spy):
    db = make_db()
    superinvestor.get_superinvestor_activity("AAPL", db=db)
    result = superinvestor.get_superinvestor_activity("NVDA", db=db)

    assert result["moves"] == []
    assert result["available"] is True


def test_stale_cache_triggers_new_scrape(fetch_and_extract_spy):
    db = make_db()
    stale = datetime.now(timezone.utc) - timedelta(days=8)
    db[SUPERINVESTOR_MOVES_CACHE].insert_one({"moves": [], "fetched_at": stale})

    superinvestor.get_superinvestor_activity("AAPL", db=db)
    assert fetch_and_extract_spy["fetch"] == 1


def test_fetch_failure_with_no_cache_degrades(monkeypatch):
    db = make_db()

    def raising_fetch(url):
        raise RuntimeError("no browser")

    monkeypatch.setattr(superinvestor, "_fetch_page_text", raising_fetch)
    result = superinvestor.get_superinvestor_activity("AAPL", db=db)

    assert result == {"moves": [], "available": False,
                       "note": "Dataroma scrape unavailable (RuntimeError)"}
    assert db[SUPERINVESTOR_MOVES_CACHE].count_documents({}) == 0
