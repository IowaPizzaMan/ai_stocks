"""Router tests for the company profile / peers / employee-count endpoints.
Spec: specs/029-company-profile-tweaks/contracts/company-profile-api.md
"""
from datetime import datetime, timezone

from db import COMPANY_INFO, TICKER_INDEX

NOW = datetime(2026, 8, 22, 14, 3, 0, tzinfo=timezone.utc)

PROFILE = {
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "exchange_full": "NASDAQ Global Select",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "country": "US",
    "currency": "USD",
    "website": "https://www.apple.com",
    "ceo": "Timothy D. Cook",
    "full_time_employees": 166000,
    "ipo_date": "1980-12-12",
    "description": "Apple Inc. is a global technology corporation.",
    "image": "https://images.financialmodelingprep.com/symbol/AAPL.png",
    "default_image": False,
    "market_cap": 4543533578600,
    "beta": 1.086,
    "last_dividend": 1.05,
    "range": "224.69-344.57",
    "average_volume": 53759263,
    "price": 309.35,
    "change": -1.95,
    "change_percentage": -0.62641,
    "volume": 42216056,
    "is_etf": False,
    "is_fund": False,
    "is_actively_trading": True,
}


def _seed_company_info(db, ticker="AAPL", **overrides):
    doc = {
        "ticker": ticker,
        "profile": PROFILE,
        "profile_fetched_at": NOW,
        "profile_outcome": "confirmed",
        "peers": [{"symbol": "GOOGL", "name": "Alphabet Inc.", "price": 333.84, "market_cap": 4040168831718}],
        "peers_fetched_at": NOW,
        "peers_outcome": "confirmed",
        "employee_counts": [
            {"period_of_report": "2025-09-27", "filing_date": "2025-10-31", "form_type": "10-K",
             "employee_count": 166000, "source": "https://www.sec.gov/x"},
        ],
        "employee_counts_fetched_at": NOW,
        "employee_counts_outcome": "confirmed",
    }
    doc.update(overrides)
    db[COMPANY_INFO].insert_one(doc)
    return doc


# --- GET /stocks/{ticker}/profile --------------------------------------------

def test_get_profile_200_maps_fields_and_splits_range(client, db):
    _seed_company_info(db)

    r = client.get("/stocks/AAPL/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Apple Inc."
    assert body["sector"] == "Technology"
    assert body["industry"] == "Consumer Electronics"
    assert body["range_low"] == 224.69
    assert body["range_high"] == 344.57
    assert body["logo_url"] == "https://images.financialmodelingprep.com/symbol/AAPL.png"


def test_get_profile_excludes_price_change_volume(client, db):
    """FR-011b — the profile's own price/change/volume must never reach the
    UI as the app's price of record."""
    _seed_company_info(db)

    body = client.get("/stocks/AAPL/profile").json()
    assert "price" not in body
    assert "change" not in body
    assert "change_percentage" not in body
    assert "volume" not in body


def test_get_profile_404_when_never_fetched(client, db):
    r = client.get("/stocks/ZZZZ/profile")
    assert r.status_code == 404


def test_get_profile_404_when_doc_exists_but_profile_null(client, db):
    """A degraded-on-first-pull ticker has a company_info doc with profile=None."""
    _seed_company_info(db, profile=None, profile_outcome="unavailable")
    r = client.get("/stocks/AAPL/profile")
    assert r.status_code == 404


def test_get_profile_default_image_yields_null_logo(client, db):
    _seed_company_info(db, profile={**PROFILE, "default_image": True})
    body = client.get("/stocks/AAPL/profile").json()
    assert body["logo_url"] is None


# --- GET /stocks/{ticker}/peers ----------------------------------------------

def test_get_peers_sorted_market_cap_desc_nulls_last_symbol_tiebreak(client, db):
    _seed_company_info(db, peers=[
        {"symbol": "B", "name": "B Co", "price": 1, "market_cap": 100},
        {"symbol": "A", "name": "A Co", "price": 1, "market_cap": None},
        {"symbol": "C", "name": "C Co", "price": 1, "market_cap": 500},
        {"symbol": "D", "name": "D Co", "price": 1, "market_cap": 100},
    ])

    body = client.get("/stocks/AAPL/peers").json()
    symbols = [p["symbol"] for p in body["peers"]]
    assert symbols == ["C", "B", "D", "A"]  # 500, then 100/100 tie broken B<D, null last


def test_get_peers_empty_is_200(client, db):
    _seed_company_info(db, peers=[])
    r = client.get("/stocks/AAPL/peers")
    assert r.status_code == 200
    assert r.json()["peers"] == []


def test_get_peers_no_company_info_doc_is_200_empty(client, db):
    r = client.get("/stocks/ZZZZ/peers")
    assert r.status_code == 200
    assert r.json()["peers"] == []


# --- GET /stocks/{ticker}/employee-count -------------------------------------

def test_get_employee_count_sorted_ascending(client, db):
    _seed_company_info(db, employee_counts=[
        {"period_of_report": "2025-09-27", "filing_date": "2025-10-31", "form_type": "10-K",
         "employee_count": 166000, "source": "s"},
        {"period_of_report": "2023-09-30", "filing_date": "2023-10-27", "form_type": "10-K",
         "employee_count": 154000, "source": "s"},
        {"period_of_report": "2024-09-28", "filing_date": "2024-11-01", "form_type": "10-K",
         "employee_count": 161000, "source": "s"},
    ])

    body = client.get("/stocks/AAPL/employee-count").json()
    periods = [r["period_of_report"] for r in body["records"]]
    assert periods == ["2023-09-30", "2024-09-28", "2025-09-27"]


def test_get_employee_count_empty_is_200(client, db):
    r = client.get("/stocks/ZZZZ/employee-count")
    assert r.status_code == 200
    assert r.json()["records"] == []


# --- GET /stocks/industries ---------------------------------------------------

def test_list_industries_sorted_distinct_tracked_only(client, db):
    db[TICKER_INDEX].insert_many([
        {"ticker": "AAPL", "status": "active", "industry": "Consumer Electronics"},
        {"ticker": "GOOGL", "status": "active", "industry": "Internet Content & Information"},
        {"ticker": "MSFT", "status": "active", "industry": "Consumer Electronics"},
        {"ticker": "DEAD", "status": "removed_from_market", "industry": "Should Be Excluded"},
        {"ticker": "NONE", "status": "active", "industry": None},
        {"ticker": "EMPTY", "status": "active", "industry": ""},
    ])

    body = client.get("/stocks/industries").json()
    assert body["industries"] == ["Consumer Electronics", "Internet Content & Information"]


def test_list_industries_empty_before_any_profile(client, db):
    r = client.get("/stocks/industries")
    assert r.status_code == 200
    assert r.json()["industries"] == []
