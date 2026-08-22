"""Congress trading disclosures — normalizer + summary math.
Spec: specs/028-dashboard-tweaks-batch US4.
Contract: specs/028-dashboard-tweaks-batch/contracts/congress-api.md
Field mapping: research.md R7 (confirmed against a user-supplied live
response; exact JSON key casing is the one part still assumed — see
tests/fixtures/senate_latest.json / house_latest.json).
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mongomock
import pytest

from tools import congress
from tools.db import CONGRESS_TRADES

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def db():
    return mongomock.MongoClient()["congress_test"]


def trade(
    trade_id="t1", ticker="AAPL", politician="Jane Doe", person_id="D000001",
    chamber="senate", transaction_type="Purchase", amount_range="$1,001 - $15,000",
    disclosure_date=None, transaction_date=None, owner="Joint",
):
    return {
        "trade_id": trade_id, "chamber": chamber, "person_id": person_id,
        "politician": politician, "district": "AR", "owner": owner,
        "ticker": ticker, "asset_description": f"{ticker} Inc", "asset_type": "Stock",
        "transaction_type": transaction_type, "amount_range": amount_range,
        "transaction_date": transaction_date or "2026-01-01",
        "disclosure_date": disclosure_date or "2026-01-15",
        "link": None, "source": "fmp", "collected_at": datetime.now(timezone.utc),
    }


# --- normalizer (T033) ---------------------------------------------------------

def test_normalize_row_builds_politician_from_first_and_last_name():
    raw = load_fixture("senate_latest.json")[0]
    row = congress._normalize_row(raw, chamber="senate")
    assert row["politician"] == "John Boozman"


def test_normalize_row_falls_back_to_office_when_names_absent():
    raw = {**load_fixture("senate_latest.json")[0], "firstName": None, "lastName": None}
    row = congress._normalize_row(raw, chamber="senate")
    assert row["politician"] == "John Boozman"  # from office


def test_normalize_row_empty_symbol_becomes_none_not_empty_string():
    raw = {**load_fixture("house_latest.json")[0], "symbol": ""}
    row = congress._normalize_row(raw, chamber="house")
    assert row["ticker"] is None


def test_normalize_row_missing_symbol_key_becomes_none():
    raw = dict(load_fixture("house_latest.json")[0])
    del raw["symbol"]
    row = congress._normalize_row(raw, chamber="house")
    assert row["ticker"] is None


def test_normalize_row_with_neither_ticker_nor_politician_is_skipped():
    raw = {"symbol": None, "firstName": None, "lastName": None, "office": None}
    assert congress._normalize_row(raw, chamber="senate") is None


def test_normalize_row_carries_person_id_from_senate_id_field():
    raw = load_fixture("senate_latest.json")[0]
    row = congress._normalize_row(raw, chamber="senate")
    assert row["person_id"] == "B001236"


def test_normalize_row_house_fixture_maps_cleanly():
    raw = load_fixture("house_latest.json")[0]
    row = congress._normalize_row(raw, chamber="house")
    assert row["ticker"] == "META"
    assert row["politician"] == "Jared Moskowitz"
    assert row["chamber"] == "house"
    assert row["transaction_type"] == "Purchase"
    assert row["amount_range"] == "$1,001 - $15,000"


# --- trade_id composite hash (T034) ---------------------------------------------

def test_trade_id_differs_for_purchase_vs_sale_same_day_same_ticker():
    base = dict(ticker="AAPL", person_id="D1", transaction_date="2026-01-01", owner="Self")
    buy_id = congress._trade_id(**base, transaction_type="Purchase", amount_range="$1-$100")
    sell_id = congress._trade_id(**base, transaction_type="Sale", amount_range="$1-$100")
    assert buy_id != sell_id


def test_trade_id_differs_for_joint_vs_self_same_trade():
    base = dict(ticker="AAPL", person_id="D1", transaction_date="2026-01-01",
                transaction_type="Purchase", amount_range="$1-$100")
    joint_id = congress._trade_id(**base, owner="Joint")
    self_id = congress._trade_id(**base, owner="Self")
    assert joint_id != self_id


def test_trade_id_stable_for_identical_inputs():
    kwargs = dict(ticker="AAPL", person_id="D1", transaction_date="2026-01-01",
                  transaction_type="Purchase", amount_range="$1-$100", owner="Self")
    assert congress._trade_id(**kwargs) == congress._trade_id(**kwargs)


# --- parse_amount_bounds (T035) -------------------------------------------------

def test_parse_amount_bounds_standard_bracket():
    assert congress.parse_amount_bounds("$1,001 - $15,000") == (1001, 15000)


def test_parse_amount_bounds_exact_threshold_boundary():
    assert congress.parse_amount_bounds("$50,001 - $100,001")[1] == 100001


def test_parse_amount_bounds_en_dash_separator():
    assert congress.parse_amount_bounds("$15,001–$50,000") == (15001, 50000)


def test_parse_amount_bounds_open_ended_over_form():
    lo, hi = congress.parse_amount_bounds("Over $1,000,000")
    assert lo == 1000000
    assert hi == 1000000  # upper == lower so a >= threshold test still works


def test_parse_amount_bounds_absent_returns_none():
    assert congress.parse_amount_bounds(None) is None


def test_parse_amount_bounds_garbage_returns_none():
    assert congress.parse_amount_bounds("not an amount") is None


# --- is_purchase (T036) ----------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("Purchase", True),
    ("purchase", True),
    ("PURCHASE", True),
    ("Sale", False),
    ("Sale (Full)", False),
    ("Sale (Partial)", False),
    ("Exchange", False),
    (None, False),
])
def test_is_purchase(value, expected):
    assert congress.is_purchase(value) is expected


# --- rank_most_bought (T037) ------------------------------------------------------

def test_rank_most_bought_counts_purchases_in_window(db):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=10)).date().isoformat()
    rows = [
        trade("t1", ticker="AAPL", disclosure_date=recent, transaction_type="Purchase"),
        trade("t2", ticker="AAPL", disclosure_date=recent, transaction_type="Purchase"),
        trade("t3", ticker="AAPL", disclosure_date=recent, transaction_type="Sale"),
        trade("t4", ticker="NVDA", disclosure_date=recent, transaction_type="Purchase"),
    ]
    ranked = congress.rank_most_bought(rows, now=now)
    assert ranked[0] == {"ticker": "AAPL", "buy_count": 2}
    assert {"ticker": "NVDA", "buy_count": 1} in ranked


def test_rank_most_bought_excludes_null_ticker(db):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=5)).date().isoformat()
    rows = [trade("t1", ticker=None, disclosure_date=recent, transaction_type="Purchase")]
    assert congress.rank_most_bought(rows, now=now) == []


def test_rank_most_bought_ties_broken_by_ticker_ascending():
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=5)).date().isoformat()
    rows = [
        trade("t1", ticker="ZWQ", disclosure_date=recent, transaction_type="Purchase"),
        trade("t2", ticker="AAPL", disclosure_date=recent, transaction_type="Purchase"),
    ]
    ranked = congress.rank_most_bought(rows, now=now)
    assert [r["ticker"] for r in ranked] == ["AAPL", "ZWQ"]


def test_rank_most_bought_window_boundary(db):
    now = datetime.now(timezone.utc)
    just_inside = (now - timedelta(days=89)).date().isoformat()
    just_outside = (now - timedelta(days=91)).date().isoformat()
    rows = [
        trade("t1", ticker="AAPL", disclosure_date=just_inside, transaction_type="Purchase"),
        trade("t2", ticker="NVDA", disclosure_date=just_outside, transaction_type="Purchase"),
    ]
    ranked = congress.rank_most_bought(rows, now=now, days=90)
    assert [r["ticker"] for r in ranked] == ["AAPL"]


# --- high_dollar (T038) -----------------------------------------------------------

def test_high_dollar_selects_on_upper_bound_at_or_above_threshold(db):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=5)).date().isoformat()
    rows = [
        trade("t1", ticker="AAPL", disclosure_date=recent, amount_range="$100,001 - $250,000"),
        trade("t2", ticker="NVDA", disclosure_date=recent, amount_range="$50,001 - $100,000"),
    ]
    flagged = congress.high_dollar(rows, now=now)
    assert [r["ticker"] for r in flagged] == ["AAPL"]


def test_high_dollar_never_derives_a_midpoint_or_point_value(db):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=5)).date().isoformat()
    rows = [trade("t1", disclosure_date=recent, amount_range="$250,001 - $500,000")]
    flagged = congress.high_dollar(rows, now=now)
    assert flagged[0]["amount_range"] == "$250,001 - $500,000"
    assert "amount" not in flagged[0]
    assert "midpoint" not in flagged[0]


def test_high_dollar_unparseable_amount_excluded_but_not_erroring(db):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=5)).date().isoformat()
    rows = [trade("t1", disclosure_date=recent, amount_range=None)]
    assert congress.high_dollar(rows, now=now) == []


def test_high_dollar_outside_window_excluded(db):
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=200)).date().isoformat()
    rows = [trade("t1", disclosure_date=old, amount_range="$1,000,001 - $5,000,000")]
    assert congress.high_dollar(rows, now=now) == []


# --- run_congress_trades_pull (T044) ------------------------------------------

def test_run_congress_trades_pull_stores_both_chambers(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        if "senate" in path:
            return load_fixture("senate_latest.json")
        return load_fixture("house_latest.json")

    monkeypatch.setattr(congress, "fmp_get", fake_fmp_get)

    count = congress.run_congress_trades_pull(db)

    assert count == 3  # 2 senate + 1 house
    assert db[CONGRESS_TRADES].count_documents({"chamber": "senate"}) == 2
    assert db[CONGRESS_TRADES].count_documents({"chamber": "house"}) == 1


def test_run_congress_trades_pull_one_chamber_failing_does_not_lose_the_other(db, monkeypatch):
    def flaky_fmp_get(path, db=None):
        if "senate" in path:
            raise ConnectionError("senate feed down")
        return load_fixture("house_latest.json")

    monkeypatch.setattr(congress, "fmp_get", flaky_fmp_get)

    count = congress.run_congress_trades_pull(db)

    assert count == 1
    assert db[CONGRESS_TRADES].count_documents({"chamber": "house"}) == 1


def test_run_congress_trades_pull_raises_when_both_chambers_fail(db, monkeypatch):
    def boom(path, db=None):
        raise ConnectionError("provider down")

    monkeypatch.setattr(congress, "fmp_get", boom)

    with pytest.raises(ConnectionError):
        congress.run_congress_trades_pull(db)


def test_run_congress_trades_pull_upsert_is_idempotent(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        if "senate" in path:
            return load_fixture("senate_latest.json")
        return load_fixture("house_latest.json")

    monkeypatch.setattr(congress, "fmp_get", fake_fmp_get)

    congress.run_congress_trades_pull(db)
    congress.run_congress_trades_pull(db)

    assert db[CONGRESS_TRADES].count_documents({}) == 3
