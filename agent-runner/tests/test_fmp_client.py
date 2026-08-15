"""Unit tests for tools/fmp_client.py — throttle, budget guard, entitlement
probe. No network; requests.get is faked throughout."""

import mongomock
import pytest
import requests

from tools import fmp_client
from tools.db import FMP_ENTITLEMENTS, FMP_USAGE


@pytest.fixture
def db():
    return mongomock.MongoClient()["fmp_client_test"]


@pytest.fixture(autouse=True)
def reset_throttle():
    """Each test gets a clean token bucket — the deque is module-global."""
    fmp_client._call_times.clear()
    yield
    fmp_client._call_times.clear()


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def json(self):
        return self._payload


def test_fmp_get_hits_url_with_api_key(monkeypatch, db):
    monkeypatch.setattr(fmp_client.settings, "fmp_api_key", "TESTKEY")
    captured = {}

    def fake_get(url, timeout=None):
        captured["url"] = url
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)
    result = fmp_client.fmp_get("quote?symbol=AAPL", db=db)

    assert result == {"ok": True}
    assert "apikey=TESTKEY" in captured["url"]
    assert captured["url"].startswith(fmp_client.FMP_BASE)


def test_fmp_get_raises_http_error_on_4xx(monkeypatch, db):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse(402))
    with pytest.raises(requests.HTTPError):
        fmp_client.fmp_get("grades?symbol=APP", db=db)


def test_daily_soft_cap_raises_once_exceeded(monkeypatch, db):
    monkeypatch.setattr(fmp_client.settings, "fmp_daily_soft_cap", 2)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse(200, {}))

    fmp_client.fmp_get("quote?symbol=A", db=db)
    fmp_client.fmp_get("quote?symbol=B", db=db)
    with pytest.raises(fmp_client.FmpBudgetExceededError):
        fmp_client.fmp_get("quote?symbol=C", db=db)


def test_daily_soft_cap_disabled_by_default(monkeypatch, db):
    assert fmp_client.settings.fmp_daily_soft_cap == 0
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse(200, {}))
    for _ in range(10):
        fmp_client.fmp_get("quote?symbol=A", db=db)
    assert db[FMP_USAGE].find_one()["count"] == 10


def test_throttle_sleeps_once_limit_hit(monkeypatch, db):
    monkeypatch.setattr(fmp_client.settings, "fmp_calls_per_minute", 2)
    slept = []
    monkeypatch.setattr(fmp_client.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse(200, {}))

    fmp_client.fmp_get("a", db=db)
    fmp_client.fmp_get("b", db=db)
    fmp_client.fmp_get("c", db=db)  # third call in-window triggers a sleep

    assert len(slept) == 1
    assert slept[0] > 0


def test_throttle_disabled_when_limit_zero(monkeypatch, db):
    monkeypatch.setattr(fmp_client.settings, "fmp_calls_per_minute", 0)
    slept = []
    monkeypatch.setattr(fmp_client.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse(200, {}))

    for _ in range(20):
        fmp_client.fmp_get("x", db=db)
    assert slept == []


def test_fetch_eod_history_shapes_like_yfinance(monkeypatch, db):
    payload = [
        {"date": "2026-08-13", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
        {"date": "2026-08-14", "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1200},
    ]
    monkeypatch.setattr(fmp_client, "fmp_get", lambda path, db=None: payload)

    df = fmp_client.fetch_eod_history("AAPL", db=db)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.index.name == "Date"
    assert df.index.is_monotonic_increasing
    assert df.iloc[0]["Close"] == 101


def test_fetch_eod_history_empty_response(monkeypatch, db):
    monkeypatch.setattr(fmp_client, "fmp_get", lambda path, db=None: [])
    df = fmp_client.fetch_eod_history("GONE", db=db)
    assert df.empty
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_entitlement_probe_records_entitled_and_payment_required(monkeypatch, db):
    def fake_get(path, db=None):
        if "grades" in path:
            resp = FakeResponse(402)
            resp.raise_for_status()
        return {"ok": True}

    monkeypatch.setattr(fmp_client, "fmp_get", fake_get)
    results = fmp_client.fmp_entitlement_probe(db=db)

    by_family = {r["family"]: r for r in results}
    assert by_family["analyst_grades"]["result"] == "payment_required"
    assert by_family["analyst_grades"]["http_status"] == 402
    assert by_family["eod_prices"]["result"] == "entitled"

    stored = list(db[FMP_ENTITLEMENTS].find({}))
    assert len(stored) == len(fmp_client.PROBE_ENDPOINTS)


def test_entitlement_probe_family_error_does_not_abort_others(monkeypatch, db):
    def fake_get(path, db=None):
        if "batch" in path.lower() or "quote" in path:
            raise RuntimeError("boom")
        return {"ok": True}

    monkeypatch.setattr(fmp_client, "fmp_get", fake_get)
    results = fmp_client.fmp_entitlement_probe(db=db)
    assert len(results) == len(fmp_client.PROBE_ENDPOINTS)
