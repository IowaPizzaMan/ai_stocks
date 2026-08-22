"""Unit tests for tools/market_movers.py — network fully faked.
Spec: specs/028-dashboard-tweaks-batch US6.
Contract: specs/028-dashboard-tweaks-batch/contracts/market-movers-api.md

FMP's most-actives endpoint returns no volume field (R9, confirmed against a
live response) — the tests below guard against re-introducing an assumption
of one, and against the fraction/percent mixup on changesPercentage.
"""
from datetime import date

import mongomock
import pytest
import requests

from tools import market_movers
from tools.db import MARKET_MOVERS

RAW_ROW = {
    "symbol": "LUCY",
    "price": 1.85,
    "name": "Innovative Eyewear, Inc.",
    "change": 0.06,
    "changesPercentage": 3.35196,
    "exchange": "NASDAQ",
}


@pytest.fixture
def db():
    return mongomock.MongoClient()["market_movers_test"]


def test_run_stores_rows_with_category_actives_and_rank(db, monkeypatch):
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [
        RAW_ROW, {**RAW_ROW, "symbol": "ZWQ", "changesPercentage": -1.2},
    ])

    count = market_movers.run_market_movers_pull(db)

    assert count == 2
    rows = list(db[MARKET_MOVERS].find({"category": "actives"}).sort("rank", 1))
    assert [r["ticker"] for r in rows] == ["LUCY", "ZWQ"]
    assert [r["rank"] for r in rows] == [0, 1]
    assert all(r["category"] == "actives" for r in rows)


def test_field_mapping_from_provider_shape(db, monkeypatch):
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [RAW_ROW])
    market_movers.run_market_movers_pull(db)

    row = db[MARKET_MOVERS].find_one({"ticker": "LUCY"})
    assert row["company"] == "Innovative Eyewear, Inc."
    assert row["price"] == 1.85
    assert row["change"] == 0.06
    assert row["exchange"] == "NASDAQ"


def test_change_pct_is_stored_as_the_percent_the_provider_sent_not_a_fraction(db, monkeypatch):
    """R9 — 3.35196 means +3.35%, not +335.20%. No *100 conversion."""
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [RAW_ROW])
    market_movers.run_market_movers_pull(db)

    row = db[MARKET_MOVERS].find_one({"ticker": "LUCY"})
    assert row["change_pct"] == pytest.approx(3.35196)


def test_no_volume_field_is_ever_populated(db, monkeypatch):
    """The most-actives endpoint supplies no volume — asserting this stays
    None (not silently defaulted to 0, which would look like real data)."""
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [RAW_ROW])
    market_movers.run_market_movers_pull(db)

    row = db[MARKET_MOVERS].find_one({"ticker": "LUCY"})
    assert row.get("volume") is None


def test_stamps_todays_date(db, monkeypatch):
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [RAW_ROW])
    market_movers.run_market_movers_pull(db)

    row = db[MARKET_MOVERS].find_one({"ticker": "LUCY"})
    assert row["date"] == date.today().isoformat()


def test_upsert_is_idempotent_on_same_day_rerun(db, monkeypatch):
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [RAW_ROW])
    market_movers.run_market_movers_pull(db)
    market_movers.run_market_movers_pull(db)

    assert db[MARKET_MOVERS].count_documents({"ticker": "LUCY", "category": "actives"}) == 1


def test_a_rerun_updates_rank_when_provider_order_changes(db, monkeypatch):
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [
        RAW_ROW, {**RAW_ROW, "symbol": "ZWQ"},
    ])
    market_movers.run_market_movers_pull(db)

    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [
        {**RAW_ROW, "symbol": "ZWQ"}, RAW_ROW,
    ])
    market_movers.run_market_movers_pull(db)

    assert db[MARKET_MOVERS].find_one({"ticker": "ZWQ"})["rank"] == 0
    assert db[MARKET_MOVERS].find_one({"ticker": "LUCY"})["rank"] == 1


def test_provider_failure_propagates_and_leaves_prior_rows_intact(db, monkeypatch):
    """Fail-soft means stored data survives a failure, not that the failure
    is hidden — the job is correctly marked failed by the caller (queue_worker)
    since no partial write happens before the fetch succeeds."""
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [RAW_ROW])
    market_movers.run_market_movers_pull(db)

    def boom(path, db=None):
        raise requests.HTTPError("503")

    monkeypatch.setattr(market_movers, "fmp_get", boom)
    with pytest.raises(requests.HTTPError):
        market_movers.run_market_movers_pull(db)

    assert db[MARKET_MOVERS].find_one({"ticker": "LUCY"}) is not None


def test_row_with_missing_symbol_is_skipped_not_stored(db, monkeypatch):
    monkeypatch.setattr(market_movers, "fmp_get", lambda path, db=None: [
        RAW_ROW, {**RAW_ROW, "symbol": None},
    ])
    count = market_movers.run_market_movers_pull(db)
    assert count == 1
    assert db[MARKET_MOVERS].count_documents({"category": "actives"}) == 1
