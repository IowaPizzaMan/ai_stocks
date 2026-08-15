"""Unit tests for tools/financials.py — FMP is faked; no network."""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

from tools import financials
from tools.db import FINANCIALS_CACHE
from tools.fmp_client import FmpBudgetExceededError


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


@pytest.fixture
def fake_fmp(monkeypatch):
    calls = []

    def _fmp_get(path, db=None):
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
    # call-count tracking now lives inside fmp_client.fmp_get itself (see
    # test_fmp_client.py) — this test mocks fmp_get entirely, so FMP_USAGE
    # is not touched here


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


def _seed_legacy_doc(db, data, fetched_at=None):
    """Insert a cache doc the way pre-018 code wrote them: no outcomes field."""
    db[FINANCIALS_CACHE].insert_one({
        "ticker": "BSX",
        "data": data,
        "fetched_at": fetched_at or datetime.now(timezone.utc),
    })


def test_warm_hit_retries_empty_keys_on_legacy_doc(db, fake_fmp):
    """The BSX bug: an all-empty legacy doc inside the 90-day window must be
    re-fetched on the next call, not served as-is (spec 018 FR-001, US1)."""
    _seed_legacy_doc(db, {k: [] for k in financials.ENDPOINTS})

    data = financials.get_financials("BSX", db=db)

    assert len(fake_fmp) == 7
    assert all(data[k] for k in financials.ENDPOINTS)
    doc = db[FINANCIALS_CACHE].find_one({"ticker": "BSX"})
    assert doc["data"] == data  # merged result persisted


def test_warm_hit_retries_only_empty_keys(db, fake_fmp):
    seeded = {k: [] for k in financials.ENDPOINTS}
    seeded["income_annual"] = [{"revenue": 1}]
    _seed_legacy_doc(db, seeded)

    data = financials.get_financials("BSX", db=db)

    assert len(fake_fmp) == 6
    assert not any("income-statement?symbol=BSX&period=annual" in p for p in fake_fmp)
    assert data["income_annual"] == [{"revenue": 1}]
    assert all(data[k] for k in financials.ENDPOINTS)


def test_partial_retry_preserves_fetched_at(db, fake_fmp):
    stamp = datetime(2026, 8, 10, tzinfo=timezone.utc)
    _seed_legacy_doc(db, {k: [] for k in financials.ENDPOINTS}, fetched_at=stamp)

    financials.get_financials("BSX", db=db)

    doc = db[FINANCIALS_CACHE].find_one({"ticker": "BSX"})
    # mongomock returns naive UTC datetimes — normalize before comparing
    assert doc["fetched_at"].replace(tzinfo=timezone.utc) == stamp  # window must not slide


def test_retry_that_fails_again_stays_empty_and_fail_soft(db, monkeypatch):
    import requests

    def _fmp_402(path, db=None):
        response = requests.Response()
        response.status_code = 402
        raise requests.HTTPError("402 Payment Required", response=response)

    monkeypatch.setattr(financials, "fmp_get", _fmp_402)
    _seed_legacy_doc(db, {k: [] for k in financials.ENDPOINTS})

    data = financials.get_financials("BSX", db=db)  # must not raise

    assert all(data[k] == [] for k in financials.ENDPOINTS)


def test_warm_hit_all_populated_makes_no_calls(db, fake_fmp):
    seeded = {k: [{"path": k}] for k in financials.ENDPOINTS}
    _seed_legacy_doc(db, seeded)

    data = financials.get_financials("BSX", db=db)

    assert fake_fmp == []
    assert data == seeded


def test_restricted_symbol_402_degrades_to_empty(db, monkeypatch):
    """This plan only covers fundamentals for a subset of symbols — a 402
    on one endpoint must not sink the whole fetch."""
    import requests

    def _fmp_get(path, db=None):
        if "income-statement" in path and "annual" in path:
            response = requests.Response()
            response.status_code = 402
            raise requests.HTTPError("402 Payment Required", response=response)
        return [{"path": path}]

    monkeypatch.setattr(financials, "fmp_get", _fmp_get)
    data = financials.get_financials("APP", db=db)

    assert data["income_annual"] == []
    assert data["balance_annual"] == [{"path": "balance-sheet-statement?symbol=APP&period=annual&limit=4"}]
    assert set(data) == set(financials.ENDPOINTS)


def test_budget_exceeded_degrades_to_empty(db, monkeypatch):
    def _raise(path, db=None):
        raise FmpBudgetExceededError("cap exceeded")

    monkeypatch.setattr(financials, "fmp_get", _raise)
    data = financials.get_financials("AAPL", db=db)

    assert set(data) == set(financials.ENDPOINTS)
    assert all(v == [] for v in data.values())


def test_full_fetch_records_outcomes_confirmed_and_unavailable(db, monkeypatch):
    """A full fetch with one key 402ing must record `unavailable` for that
    key and `confirmed` for the rest (spec 018 US2, contract outcome table)."""
    import requests

    def _fmp_get(path, db=None):
        if "income-statement" in path and "annual" in path and "growth" not in path:
            response = requests.Response()
            response.status_code = 402
            raise requests.HTTPError("402 Payment Required", response=response)
        return [{"path": path}]

    monkeypatch.setattr(financials, "fmp_get", _fmp_get)
    financials.get_financials("APP", db=db)

    doc = db[FINANCIALS_CACHE].find_one({"ticker": "APP"})
    assert doc["outcomes"]["income_annual"] == "unavailable"
    for key in financials.ENDPOINTS:
        if key != "income_annual":
            assert doc["outcomes"][key] == "confirmed"


def test_full_fetch_budget_exceeded_marks_all_unavailable(db, monkeypatch):
    def _raise(path, db=None):
        raise FmpBudgetExceededError("cap exceeded")

    monkeypatch.setattr(financials, "fmp_get", _raise)
    financials.get_financials("AAPL", db=db)

    doc = db[FINANCIALS_CACHE].find_one({"ticker": "AAPL"})
    assert all(v == "unavailable" for v in doc["outcomes"].values())


def test_confirmed_empty_payload_not_retried_on_warm_hit(db, fake_fmp):
    """A 200 response with an empty payload is a settled `confirmed` result,
    not eligible for retry (contract: HTTP 200 empty payload -> confirmed)."""
    financials.get_financials("ZZZZ", db=db)  # cold fetch, fake_fmp always returns [{"path": path}]
    # overwrite one key to look like a genuinely-empty-but-confirmed result
    db[FINANCIALS_CACHE].update_one(
        {"ticker": "ZZZZ"},
        {"$set": {"data.growth": [], "outcomes.growth": "confirmed"}},
    )
    fake_fmp.clear()

    data = financials.get_financials("ZZZZ", db=db)

    assert fake_fmp == []  # growth not retried despite being empty
    assert data["growth"] == []


def test_warm_hit_retry_promotes_unavailable_to_confirmed(db, fake_fmp):
    """A retry that succeeds must flip `outcomes[key]` from unavailable to
    confirmed, so a third call makes zero fetches (data-model.md transitions)."""
    seeded = {k: [{"path": k}] for k in financials.ENDPOINTS}
    seeded["ratios"] = []
    outcomes = {k: "confirmed" for k in financials.ENDPOINTS}
    outcomes["ratios"] = "unavailable"
    db[FINANCIALS_CACHE].insert_one({
        "ticker": "BSX",
        "data": seeded,
        "outcomes": outcomes,
        "fetched_at": datetime.now(timezone.utc),
    })

    financials.get_financials("BSX", db=db)
    doc = db[FINANCIALS_CACHE].find_one({"ticker": "BSX"})
    assert doc["outcomes"]["ratios"] == "confirmed"

    fake_fmp.clear()
    financials.get_financials("BSX", db=db)
    assert fake_fmp == []  # third call: fully confirmed, zero fetches


def test_financials_cache_doc_invariant_data_outcomes_match_endpoints(db, fake_fmp):
    """Whenever a doc is written, outcomes and data cover exactly ENDPOINTS,
    and every unavailable key has data[key] == [] (data-model.md validation)."""
    financials.get_financials("AAPL", db=db)

    doc = db[FINANCIALS_CACHE].find_one({"ticker": "AAPL"})
    assert set(doc["data"]) == set(financials.ENDPOINTS)
    assert set(doc["outcomes"]) == set(financials.ENDPOINTS)
    for key, outcome in doc["outcomes"].items():
        if outcome == "unavailable":
            assert doc["data"][key] == []


def test_get_earnings_data_degrades_per_section(monkeypatch):
    def _fmp_get(path, db=None):
        if path.startswith("earnings?"):
            return [{"date": "2026-07-28", "epsActual": 1.1}, {"date": "2026-04-28", "epsActual": 1.0}]
        if path.startswith("analyst-estimates"):
            return [{"date": "2026-10-01", "estimatedEpsAvg": 1.2}]
        if path.startswith("grades"):
            raise RuntimeError("endpoint down")
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(financials, "fmp_get", _fmp_get)
    data = financials.get_earnings_data("AAPL")

    assert len(data["earnings_dates"]) == 2
    assert data["eps_trend"] == {}  # documented drop — no FMP equivalent
    assert data["eps_revisions"] == []  # documented drop — no FMP equivalent
    assert data["forward_estimates"] == [{"date": "2026-10-01", "estimatedEpsAvg": 1.2}]
    assert data["analyst_recs"] == []  # failed section degrades, doesn't raise
