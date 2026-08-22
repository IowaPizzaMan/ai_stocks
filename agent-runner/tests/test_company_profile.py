"""Unit tests for tools/company_profile.py — FMP is faked; no network.
Spec: specs/029-company-profile-tweaks/contracts/company-profile-api.md
"""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest
import requests

from tools import company_profile
from tools.db import COMPANY_INFO, TICKER_INDEX
from tools.fmp_client import FmpBudgetExceededError


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


RAW_PROFILE = {
    "symbol": "AAPL",
    "companyName": "Apple Inc.",
    "exchange": "NASDAQ",
    "exchangeFullName": "NASDAQ Global Select",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "country": "US",
    "currency": "USD",
    "website": "https://www.apple.com",
    "ceo": "Timothy D. Cook",
    "fullTimeEmployees": 166000,
    "ipoDate": "1980-12-12",
    "description": "Apple Inc. is a global technology corporation.",
    "image": "https://images.financialmodelingprep.com/symbol/AAPL.png",
    "defaultImage": False,
    "marketCap": 4543533578600,
    "beta": 1.086,
    "lastDividend": 1.05,
    "range": "224.69-344.57",
    "averageVolume": 53759263,
    "price": 309.35,
    "change": -1.95,
    "changePercentage": -0.62641,
    "volume": 42216056,
    "isEtf": False,
    "isFund": False,
    "isAdr": False,
    "isActivelyTrading": True,
}

RAW_PEER = {"symbol": "GOOGL", "companyName": "Alphabet Inc.", "price": 333.84, "mktCap": 4040168831718}

RAW_EMPLOYEE_RECORD = {
    "symbol": "AAPL",
    "periodOfReport": "2025-09-27",
    "filingDate": "2025-10-31",
    "formType": "10-K",
    "employeeCount": 166000,
    "source": "https://www.sec.gov/Archives/edgar/data",
}


@pytest.fixture
def fake_fmp(monkeypatch):
    calls = []

    def _fmp_get(path, db=None):
        calls.append(path)
        if path.startswith("profile"):
            return [RAW_PROFILE]
        if path.startswith("stock-peers"):
            return [RAW_PEER]
        if path.startswith("historical-employee-count"):
            return [RAW_EMPLOYEE_RECORD]
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(company_profile, "fmp_get", _fmp_get)
    return calls


def _http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status}", response=response)


# --- get_profile ------------------------------------------------------------

def test_get_profile_normalizes_and_confirms(db, fake_fmp):
    profile, outcome = company_profile.get_profile("aapl", db=db)
    assert outcome == "confirmed"
    assert profile["name"] == "Apple Inc."
    assert profile["sector"] == "Technology"
    assert profile["industry"] == "Consumer Electronics"
    assert profile["market_cap"] == 4543533578600
    assert profile["default_image"] is False
    # provider's own range string is preserved, not split, at this layer
    assert profile["range"] == "224.69-344.57"
    assert fake_fmp == ["profile?symbol=aapl"]


def test_get_profile_402_degrades(db, monkeypatch):
    monkeypatch.setattr(company_profile, "fmp_get", lambda path, db=None: (_ for _ in ()).throw(_http_error(402)))
    profile, outcome = company_profile.get_profile("AAPL", db=db)
    assert profile is None
    assert outcome == "unavailable"


def test_get_profile_budget_exceeded_degrades(db, monkeypatch):
    def _raise(path, db=None):
        raise FmpBudgetExceededError("cap exceeded")

    monkeypatch.setattr(company_profile, "fmp_get", _raise)
    profile, outcome = company_profile.get_profile("AAPL", db=db)
    assert profile is None
    assert outcome == "unavailable"


def test_get_profile_non_entitlement_error_reraises(db, monkeypatch):
    monkeypatch.setattr(company_profile, "fmp_get", lambda path, db=None: (_ for _ in ()).throw(_http_error(500)))
    with pytest.raises(requests.HTTPError):
        company_profile.get_profile("AAPL", db=db)


# --- get_peers ---------------------------------------------------------------

def test_get_peers_normalizes(db, fake_fmp):
    peers, outcome = company_profile.get_peers("AAPL", db=db)
    assert outcome == "confirmed"
    assert peers == [{"symbol": "GOOGL", "name": "Alphabet Inc.", "price": 333.84, "market_cap": 4040168831718}]


def test_get_peers_402_degrades_to_empty(db, monkeypatch):
    monkeypatch.setattr(company_profile, "fmp_get", lambda path, db=None: (_ for _ in ()).throw(_http_error(403)))
    peers, outcome = company_profile.get_peers("AAPL", db=db)
    assert peers == []
    assert outcome == "unavailable"


# --- get_employee_counts ------------------------------------------------------

def test_get_employee_counts_normalizes_and_sorts(db, monkeypatch):
    rows = [
        {**RAW_EMPLOYEE_RECORD, "periodOfReport": "2025-09-27", "employeeCount": 166000},
        {**RAW_EMPLOYEE_RECORD, "periodOfReport": "2024-09-28", "employeeCount": 150000},
    ]
    monkeypatch.setattr(company_profile, "fmp_get", lambda path, db=None: rows)

    records, outcome = company_profile.get_employee_counts("AAPL", db=db)
    assert outcome == "confirmed"
    assert [r["period_of_report"] for r in records] == ["2024-09-28", "2025-09-27"]  # ascending


def test_get_employee_counts_budget_exceeded_degrades(db, monkeypatch):
    def _raise(path, db=None):
        raise FmpBudgetExceededError("cap")

    monkeypatch.setattr(company_profile, "fmp_get", _raise)
    records, outcome = company_profile.get_employee_counts("AAPL", db=db)
    assert records == []
    assert outcome == "unavailable"


# --- refresh_company_info: orchestration -------------------------------------

def test_cold_refresh_fetches_all_three_and_writes_company_info(db, fake_fmp):
    doc = company_profile.refresh_company_info("aapl", db=db)

    assert len(fake_fmp) == 3
    assert doc["profile"]["name"] == "Apple Inc."
    assert doc["peers"] == [{"symbol": "GOOGL", "name": "Alphabet Inc.", "price": 333.84, "market_cap": 4040168831718}]
    assert len(doc["employee_counts"]) == 1
    assert doc["profile_outcome"] == doc["peers_outcome"] == doc["employee_counts_outcome"] == "confirmed"

    stored = db[COMPANY_INFO].find_one({"ticker": "AAPL"})
    assert stored["profile"]["name"] == "Apple Inc."


def test_warm_delta_refetches_profile_only(db, fake_fmp):
    company_profile.refresh_company_info("AAPL", db=db)
    fake_fmp.clear()

    company_profile.refresh_company_info("AAPL", db=db)

    assert fake_fmp == ["profile?symbol=AAPL"]  # peers/employees stayed within the 90-day window


def test_full_mode_bypasses_all_windows(db, fake_fmp):
    company_profile.refresh_company_info("AAPL", db=db)
    fake_fmp.clear()

    company_profile.refresh_company_info("AAPL", mode="full", db=db)

    assert sorted(fake_fmp) == sorted([
        "profile?symbol=AAPL", "stock-peers?symbol=AAPL", "historical-employee-count?symbol=AAPL",
    ])


def test_stale_peers_window_triggers_refetch(db, fake_fmp):
    company_profile.refresh_company_info("AAPL", db=db)
    stale = datetime.now(timezone.utc) - timedelta(days=company_profile.CACHE_DAYS + 1)
    db[COMPANY_INFO].update_one({"ticker": "AAPL"}, {"$set": {"peers_fetched_at": stale}})
    fake_fmp.clear()

    company_profile.refresh_company_info("AAPL", db=db)

    assert "stock-peers?symbol=AAPL" in fake_fmp
    assert "historical-employee-count?symbol=AAPL" not in fake_fmp  # its own window still warm


def test_unavailable_outcome_retried_next_pull_without_sliding_other_windows(db, monkeypatch):
    """The spec-018 lesson: a 402-degraded dataset must retry on the very next
    pull regardless of the 90-day window, and that retry must not reset the
    other datasets' fetched_at (data-model.md freshness rules)."""
    calls = []

    def _fmp_get_peers_402(path, db=None):
        calls.append(path)
        if path.startswith("stock-peers"):
            raise _http_error(402)
        if path.startswith("profile"):
            return [RAW_PROFILE]
        if path.startswith("historical-employee-count"):
            return [RAW_EMPLOYEE_RECORD]
        raise AssertionError(path)

    monkeypatch.setattr(company_profile, "fmp_get", _fmp_get_peers_402)
    company_profile.refresh_company_info("AAPL", db=db)

    doc = db[COMPANY_INFO].find_one({"ticker": "AAPL"})
    assert doc["peers_outcome"] == "unavailable"
    assert doc["peers"] == []
    employees_fetched_at_first = doc["employee_counts_fetched_at"]

    # second pull: peers now succeeds, employees' window is untouched
    calls.clear()

    def _fmp_get_all_ok(path, db=None):
        calls.append(path)
        if path.startswith("profile"):
            return [RAW_PROFILE]
        if path.startswith("stock-peers"):
            return [RAW_PEER]
        if path.startswith("historical-employee-count"):
            return [RAW_EMPLOYEE_RECORD]
        raise AssertionError(path)

    monkeypatch.setattr(company_profile, "fmp_get", _fmp_get_all_ok)
    company_profile.refresh_company_info("AAPL", db=db)

    doc = db[COMPANY_INFO].find_one({"ticker": "AAPL"})
    assert doc["peers_outcome"] == "confirmed"
    assert doc["peers"] == [{"symbol": "GOOGL", "name": "Alphabet Inc.", "price": 333.84, "market_cap": 4040168831718}]
    assert "stock-peers?symbol=AAPL" in calls
    # employees was warm on the second pull too — window did not slide, so it
    # was not refetched, and its fetched_at is unchanged
    assert "historical-employee-count?symbol=AAPL" not in calls
    assert doc["employee_counts_fetched_at"] == employees_fetched_at_first


def test_refresh_never_raises_on_provider_failure(db, monkeypatch):
    def _raise(path, db=None):
        raise FmpBudgetExceededError("cap exceeded")

    monkeypatch.setattr(company_profile, "fmp_get", _raise)
    doc = company_profile.refresh_company_info("AAPL", db=db)  # must not raise

    assert doc["profile_outcome"] == "unavailable"
    assert doc["profile"] is None


def test_degraded_profile_preserves_prior_stored_value(db, fake_fmp, monkeypatch):
    company_profile.refresh_company_info("AAPL", db=db)  # cold, confirmed

    def _raise(path, db=None):
        raise FmpBudgetExceededError("cap")

    monkeypatch.setattr(company_profile, "fmp_get", _raise)
    doc = company_profile.refresh_company_info("AAPL", db=db)

    assert doc["profile_outcome"] == "unavailable"
    assert doc["profile"]["name"] == "Apple Inc."  # prior value kept, not wiped to None


# --- ticker_index denormalization (research R3) -------------------------------

def test_refresh_denormalizes_sector_industry_logo_onto_ticker_index(db, fake_fmp):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})

    company_profile.refresh_company_info("AAPL", db=db)

    idx = db[TICKER_INDEX].find_one({"ticker": "AAPL"})
    assert idx["sector"] == "Technology"
    assert idx["industry"] == "Consumer Electronics"
    assert idx["name"] == "Apple Inc."
    assert idx["logo_url"] == "https://images.financialmodelingprep.com/symbol/AAPL.png"


def test_default_image_yields_null_logo_url(db, monkeypatch):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})
    placeholder = {**RAW_PROFILE, "defaultImage": True}
    monkeypatch.setattr(company_profile, "fmp_get", lambda path, db=None: [placeholder] if path.startswith("profile") else [])

    company_profile.refresh_company_info("AAPL", db=db)

    idx = db[TICKER_INDEX].find_one({"ticker": "AAPL"})
    assert idx["logo_url"] is None


def test_degraded_profile_does_not_touch_ticker_index(db, monkeypatch):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "sector": "Existing"})

    def _raise(path, db=None):
        raise FmpBudgetExceededError("cap")

    monkeypatch.setattr(company_profile, "fmp_get", _raise)
    company_profile.refresh_company_info("AAPL", db=db)

    idx = db[TICKER_INDEX].find_one({"ticker": "AAPL"})
    assert idx["sector"] == "Existing"  # untouched — no profile to denormalize from
