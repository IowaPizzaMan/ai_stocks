"""Backend FMP budget guard — specs/022-market-news-feed (Principle IV).

The backend previously had no budget accounting at all: routers/price.py and
earnings_data.py call FMP with bare requests.get and never touch the counter
agent-runner's guard reads. These tests pin the contract for the new shared
guard so both services throttle against one number.
"""
from datetime import datetime, timezone

import pytest
import requests

import fmp
from db import FMP_USAGE


class FakeResp:
    def __init__(self, payload=None, status=200):
        self._payload = payload if payload is not None else []
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


def today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_counter_increments_on_the_utc_day_bucket(db, monkeypatch):
    monkeypatch.setattr(fmp.requests, "get", lambda url, timeout=15: FakeResp([{"a": 1}]))

    fmp.fmp_get("news/stock-latest", db=db)
    fmp.fmp_get("news/stock-latest", db=db)

    doc = db[FMP_USAGE].find_one({"date": today_key()})
    assert doc["count"] == 2


def test_returns_parsed_json(db, monkeypatch):
    monkeypatch.setattr(fmp.requests, "get", lambda url, timeout=15: FakeResp([{"symbol": "AAPL"}]))
    assert fmp.fmp_get("news/stock-latest", db=db) == [{"symbol": "AAPL"}]


def test_appends_the_api_key_and_uses_the_stable_base(db, monkeypatch):
    seen = {}

    def fake_get(url, timeout=15):
        seen["url"] = url
        return FakeResp()

    monkeypatch.setattr(fmp.requests, "get", fake_get)
    monkeypatch.setattr(fmp.settings, "fmp_api_key", "TESTKEY")

    fmp.fmp_get("news/stock-latest?limit=20", db=db)

    assert seen["url"].startswith("https://financialmodelingprep.com/stable/")
    assert "apikey=TESTKEY" in seen["url"]
    # path already had a query string, so the key must be joined with &
    assert "limit=20&apikey=" in seen["url"]


def test_soft_cap_of_zero_never_raises(db, monkeypatch):
    monkeypatch.setattr(fmp.requests, "get", lambda url, timeout=15: FakeResp())
    monkeypatch.setattr(fmp.settings, "fmp_daily_soft_cap", 0)

    for _ in range(25):
        fmp.fmp_get("news/stock-latest", db=db)

    assert db[FMP_USAGE].find_one({"date": today_key()})["count"] == 25


def test_exceeding_a_non_zero_cap_raises(db, monkeypatch):
    monkeypatch.setattr(fmp.requests, "get", lambda url, timeout=15: FakeResp())
    monkeypatch.setattr(fmp.settings, "fmp_daily_soft_cap", 2)

    fmp.fmp_get("news/stock-latest", db=db)
    fmp.fmp_get("news/stock-latest", db=db)
    with pytest.raises(fmp.FmpBudgetExceededError):
        fmp.fmp_get("news/stock-latest", db=db)


def test_budget_check_happens_before_the_request(db, monkeypatch):
    """A blown cap must not still spend the call it was meant to prevent."""
    calls = []

    def fake_get(url, timeout=15):
        calls.append(url)
        return FakeResp()

    monkeypatch.setattr(fmp.requests, "get", fake_get)
    monkeypatch.setattr(fmp.settings, "fmp_daily_soft_cap", 1)

    fmp.fmp_get("news/stock-latest", db=db)
    with pytest.raises(fmp.FmpBudgetExceededError):
        fmp.fmp_get("news/stock-latest", db=db)

    assert len(calls) == 1


def test_http_errors_propagate_for_the_caller_to_degrade(db, monkeypatch):
    monkeypatch.setattr(fmp.requests, "get", lambda url, timeout=15: FakeResp(status=502))
    with pytest.raises(requests.HTTPError):
        fmp.fmp_get("news/stock-latest", db=db)
