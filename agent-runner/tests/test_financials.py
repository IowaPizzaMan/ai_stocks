"""Unit tests for tools/financials.py — FMP and yfinance are faked; no network."""
from datetime import datetime, timedelta, timezone

import mongomock
import pandas as pd
import pytest

from tools import financials
from tools.db import FINANCIALS_CACHE, FMP_USAGE


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


@pytest.fixture
def fake_fmp(monkeypatch):
    calls = []

    def _fmp_get(path):
        calls.append(path)
        return [{"path": path}]

    monkeypatch.setattr(financials, "fmp_get", _fmp_get)
    return calls


def test_cold_fetch_hits_all_endpoints_and_caches(db, fake_fmp):
    data = financials.get_financials("aapl", db=db)

    assert set(data) == set(financials.ENDPOINTS)
    assert len(fake_fmp) == 7
    assert all("AAPL" in p for p in fake_fmp)

    doc = db[FINANCIALS_CACHE].find_one({"ticker": "AAPL"})
    assert doc is not None and doc["data"] == data
    assert db[FMP_USAGE].find_one()["count"] == 7


def test_warm_cache_makes_no_fmp_calls(db, fake_fmp):
    financials.get_financials("AAPL", db=db)
    fake_fmp.clear()

    again = financials.get_financials("AAPL", db=db)
    assert fake_fmp == []
    assert set(again) == set(financials.ENDPOINTS)


def test_stale_cache_refetches(db, fake_fmp):
    stale = datetime.now(timezone.utc) - timedelta(days=financials.CACHE_DAYS + 1)
    db[FINANCIALS_CACHE].insert_one({"ticker": "AAPL", "data": {"old": True}, "fetched_at": stale})

    data = financials.get_financials("AAPL", db=db)
    assert "old" not in data
    assert len(fake_fmp) == 7
    # cache doc replaced, not duplicated
    assert db[FINANCIALS_CACHE].count_documents({"ticker": "AAPL"}) == 1


def test_quota_guard_skips_non_essential(db, fake_fmp):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db[FMP_USAGE].insert_one({"date": today, "count": financials.SKIP_NON_ESSENTIAL_AT - 1})

    data = financials.get_financials("AAPL", db=db)

    essential = [k for k, (_, ess) in financials.ENDPOINTS.items() if ess]
    non_essential = [k for k, (_, ess) in financials.ENDPOINTS.items() if not ess]
    assert len(fake_fmp) == len(essential)
    for k in non_essential:
        assert data[k] == []
    for k in essential:
        assert data[k] != []


class FakeEarningsTicker:
    def __init__(self, symbol):
        idx = pd.date_range("2026-01-01", periods=2, freq="QE", name="Earnings Date")
        self._dates = pd.DataFrame({"EPS Estimate": [1.0, 1.1]}, index=idx)
        self._frame = pd.DataFrame({"a": [1]})

    def get_earnings_dates(self, limit=8):
        return self._dates

    def get_eps_trend(self):
        return self._frame

    def get_eps_revisions(self):
        raise RuntimeError("endpoint down")

    def get_earnings_estimate(self):
        return self._frame

    def get_recommendations(self):
        return self._frame


def test_get_earnings_data_degrades_per_section(monkeypatch):
    monkeypatch.setattr(financials.yf, "Ticker", FakeEarningsTicker)
    data = financials.get_earnings_data("AAPL")

    assert len(data["earnings_dates"]) == 2
    assert data["eps_trend"] == {"a": {0: 1}}
    assert data["eps_revisions"] == []  # failed section degrades, doesn't raise
    assert data["analyst_recs"] == [{"a": 1}]
