"""Pure signal derivation + persistence for the `strategy_signals` collection.
Spec: specs/032-weekly-strategy-picks; data-model.md.

compute_signals() only aggregates fields skills/the_strat.py and
skills/gap_analysis.py already compute — these tests exercise the
aggregation rules (direction/strength/entry-price selection, insufficient-
history propagation), not the underlying pattern-detection/scoring logic,
which is already covered by test_the_strat.py / test_gap_analysis.py.
"""
from datetime import datetime, timezone

import mongomock
import pandas as pd
import pytest

from skills import the_strat
from tools import strategy_signals
from tools.db import PRICE_HISTORY, STRATEGY_SIGNALS

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)
BASE = (100, 110, 90, 105)  # wide reference bar, matches test_the_strat.py


def bars(rows):
    """rows: list of (open, high, low, close) tuples. Includes a flat Volume
    column too — the_strat.py doesn't need one, but gap_analysis.py does, and
    compute_signals() feeds the same price_data to both skills."""
    idx = pd.date_range("2026-06-01", periods=len(rows), freq="B")
    return pd.DataFrame(
        {
            "Open": [r[0] for r in rows], "High": [r[1] for r in rows],
            "Low": [r[2] for r in rows], "Close": [r[3] for r in rows],
            "Volume": 1_000_000,
        },
        index=idx,
    )


def price_data(daily, weekly, monthly, quarterly=None, yearly=None):
    return {
        "daily": daily, "weekly": weekly, "monthly": monthly,
        "quarterly": monthly if quarterly is None else quarterly,
        "yearly": monthly if yearly is None else yearly,
    }


def flat_days(n, price=100.0, volume=1_000_000, start="2026-03-02"):
    dates = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame(
        {"Open": price, "High": price + 1.0, "Low": price - 1.0,
         "Close": price + 0.5, "Volume": volume},
        index=dates,
    )


def add_day(df, open_, high, low, close, volume):
    nxt = df.index[-1] + pd.tseries.offsets.BDay(1)
    row = pd.DataFrame(
        {"Open": [open_], "High": [high], "Low": [low], "Close": [close], "Volume": [volume]},
        index=[nxt],
    )
    return pd.concat([df, row])


# --- STRATEGY_SIGNALS constant pin (mirrored in backend/tests/test_db_constants.py) ---

def test_strategy_signals_constant_pinned():
    """Mirrored verbatim in backend/tests/test_db_constants.py — the two
    services share no Python package, so this pinned-value pair IS the
    cross-service consistency check (constitution Principle VI)."""
    assert STRATEGY_SIGNALS == "strategy_signals"


# --- _the_strat_block ---------------------------------------------------------

def test_the_strat_block_full_bullish_with_weekly_trigger():
    daily = bars([BASE, (100, 111, 95, 110)])
    weekly = bars([BASE, (100, 108, 92, 104), (100, 106, 85, 103)])  # revstrat_2bar_bullish, buy_trigger=106
    monthly = bars([BASE, (99, 113, 95, 110)])
    quarterly = bars([BASE, (98, 114, 95, 110)])
    yearly = bars([BASE, (95, 115, 90, 110)])
    strat_out_data = price_data(daily, weekly, monthly, quarterly, yearly)
    strat_out = the_strat.run("AAPL", strat_out_data)
    assert strat_out["tfc"]["status"] == "full_bullish"

    block = strategy_signals._the_strat_block(strat_out)
    assert block == {
        "direction": "long", "pattern": "revstrat_2bar_bullish",
        "timeframe": "weekly", "entry_price": 106.0, "strength": 1,
    }


def test_the_strat_block_falls_back_to_monthly_when_weekly_has_no_trigger():
    daily = bars([BASE, (100, 111, 95, 110)])
    weekly = bars([BASE, (100, 112, 95, 110)])  # only 2 bars -> no detectable pattern
    monthly = bars([BASE, (100, 108, 92, 104), (100, 106, 85, 103)])  # revstrat_2bar_bullish
    quarterly = bars([BASE, (98, 114, 95, 110)])
    yearly = bars([BASE, (95, 115, 90, 110)])
    strat_out = the_strat.run("AAPL", price_data(daily, weekly, monthly, quarterly, yearly))
    assert strat_out["tfc"]["status"] == "full_bullish"

    block = strategy_signals._the_strat_block(strat_out)
    assert block["timeframe"] == "monthly"
    assert block["entry_price"] == 106.0
    assert block["strength"] == 1


def test_the_strat_block_null_when_no_pattern_backs_aligned_tfc():
    daily = bars([BASE, (100, 111, 95, 110)])
    weekly = bars([BASE, (100, 112, 95, 110)])
    monthly = bars([BASE, (99, 113, 95, 110)])
    quarterly = bars([BASE, (98, 114, 95, 110)])
    yearly = bars([BASE, (95, 115, 90, 110)])
    strat_out = the_strat.run("AAPL", price_data(daily, weekly, monthly, quarterly, yearly))
    assert strat_out["tfc"]["status"] == "full_bullish"
    assert strategy_signals._the_strat_block(strat_out) == strategy_signals.NULL_THE_STRAT


def test_the_strat_block_null_on_tfc_conflict():
    daily = bars([BASE, (100, 111, 95, 110)])
    weekly = bars([BASE, (115, 118, 95, 110)])  # red -> conflict
    monthly = bars([BASE, (99, 113, 95, 110)])
    strat_out = the_strat.run("AAPL", price_data(daily, weekly, monthly))
    assert strat_out["tfc"]["status"] == "conflict"
    assert strategy_signals._the_strat_block(strat_out) == strategy_signals.NULL_THE_STRAT


def test_the_strat_block_null_on_insufficient_history():
    one_bar = bars([BASE])
    strat_out = the_strat.run("AAPL", price_data(one_bar, one_bar, one_bar))
    assert strat_out["tfc"] is None
    assert strategy_signals._the_strat_block(strat_out) == strategy_signals.NULL_THE_STRAT


def test_the_strat_block_excludes_kicking_pattern_from_entry():
    daily = bars([BASE, (100, 118, 95, 115)])
    weekly = bars([BASE, (104, 106, 96, 98), (108, 112, 107, 111)])  # kicking_bullish only
    monthly = bars([BASE, (99, 120, 95, 115)])
    quarterly = bars([BASE, (98, 121, 95, 115)])
    yearly = bars([BASE, (95, 122, 90, 115)])
    strat_out = the_strat.run("AAPL", price_data(daily, weekly, monthly, quarterly, yearly))
    assert strat_out["tfc"]["status"] == "full_bullish"
    assert [p["name"] for p in strat_out["timeframes"]["weekly"]["patterns"]] == ["kicking_bullish"]

    assert strategy_signals._the_strat_block(strat_out) == strategy_signals.NULL_THE_STRAT


def test_the_strat_block_short_direction_uses_sell_trigger():
    daily = bars([BASE, (95, 100, 88, 90)])
    weekly = bars([BASE, (105, 115, 95, 112), (110, 114, 85, 88)])  # 22_reversal_bearish, sell_trigger=85
    monthly = bars([BASE, (101, 106, 85, 88)])
    quarterly = bars([BASE, (102, 107, 85, 88)])
    yearly = bars([BASE, (105, 110, 85, 88)])
    strat_out = the_strat.run("AAPL", price_data(daily, weekly, monthly, quarterly, yearly))
    assert strat_out["tfc"]["status"] == "full_bearish"

    block = strategy_signals._the_strat_block(strat_out)
    assert block["direction"] == "short"
    assert block["pattern"] == "22_reversal_bearish"
    assert block["entry_price"] == 85.0


# --- _gap_analysis_block -------------------------------------------------------

def test_gap_analysis_block_long_on_qualifying_down_gap():
    gap_out = {"latest_gap": {"direction": "down", "score": 4, "reversal_level": 99.0,
                              "bias": "LONG at day 3+"}}
    assert strategy_signals._gap_analysis_block(gap_out) == {
        "direction": "long", "score": 4, "entry_price": 99.0, "bias": "LONG at day 3+",
    }


def test_gap_analysis_block_short_on_qualifying_up_gap():
    gap_out = {"latest_gap": {"direction": "up", "score": 5, "reversal_level": 101.0,
                              "bias": "SHORT days 1-10, LONG by day 30"}}
    block = strategy_signals._gap_analysis_block(gap_out)
    assert block["direction"] == "short"
    assert block["entry_price"] == 101.0


def test_gap_analysis_block_null_below_score_threshold():
    gap_out = {"latest_gap": {"direction": "down", "score": 2, "reversal_level": 99.0, "bias": "x"}}
    assert strategy_signals._gap_analysis_block(gap_out) == strategy_signals.NULL_GAP_ANALYSIS


def test_gap_analysis_block_null_when_no_gap():
    assert strategy_signals._gap_analysis_block({"latest_gap": None}) == strategy_signals.NULL_GAP_ANALYSIS


# --- compute_signals (integration of both blocks) ------------------------------

def test_compute_signals_insufficient_history_nulls_both_blocks():
    one_bar = bars([BASE])
    doc = strategy_signals.compute_signals(
        "aapl", price_data(one_bar, one_bar, one_bar), now=NOW
    )
    assert doc["ticker"] == "AAPL"
    assert doc["insufficient_history"] is True
    assert doc["the_strat"] == strategy_signals.NULL_THE_STRAT
    assert doc["gap_analysis"] == strategy_signals.NULL_GAP_ANALYSIS
    assert doc["signals_as_of"] == NOW


def test_compute_signals_is_pure():
    daily = bars([BASE, (100, 111, 95, 110)])
    data = price_data(daily, daily, daily)
    doc1 = strategy_signals.compute_signals("AAPL", data, now=NOW)
    doc2 = strategy_signals.compute_signals("AAPL", data, now=NOW)
    assert doc1 == doc2


def test_compute_signals_surfaces_a_qualifying_gap():
    df = flat_days(40)
    df = add_day(df, 101.0, 101.5, 99.0, 99.2, 1_000_000)   # black day, Low=99.0
    df = add_day(df, 96.5, 97.0, 96.0, 96.8, 400_000)       # gap down
    doc = strategy_signals.compute_signals("AAPL", price_data(df, df, df), now=NOW)
    assert doc["insufficient_history"] is False
    assert doc["gap_analysis"]["direction"] == "long"
    assert doc["gap_analysis"]["entry_price"] == 99.0
    assert doc["gap_analysis"]["score"] is not None and doc["gap_analysis"]["score"] >= 3


# --- refresh_all / refresh_one / run_strategy_signals_refresh (mongomock) -----

@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


def _empty_price_data(ticker, db=None):
    return {"daily": [], "weekly": [], "monthly": [], "quarterly": [], "yearly": []}


def test_refresh_all_writes_one_doc_per_price_history_ticker(db, monkeypatch):
    db[PRICE_HISTORY].insert_many([{"ticker": "AAPL"}, {"ticker": "MSFT"}])
    monkeypatch.setattr(strategy_signals, "get_price_history", _empty_price_data)

    count = strategy_signals.refresh_all(db)

    assert count == 2
    assert db[STRATEGY_SIGNALS].count_documents({}) == 2
    doc = db[STRATEGY_SIGNALS].find_one({"ticker": "AAPL"})
    assert doc["insufficient_history"] is True


def test_refresh_all_skips_ticker_on_price_data_error(db, monkeypatch):
    db[PRICE_HISTORY].insert_many([{"ticker": "AAPL"}, {"ticker": "BAD"}])

    def flaky(ticker, db=None):
        if ticker == "BAD":
            raise RuntimeError("boom")
        return _empty_price_data(ticker, db=db)

    monkeypatch.setattr(strategy_signals, "get_price_history", flaky)

    count = strategy_signals.refresh_all(db)

    assert count == 1
    assert db[STRATEGY_SIGNALS].count_documents({}) == 1
    assert db[STRATEGY_SIGNALS].find_one({"ticker": "BAD"}) is None


def test_refresh_one_returns_none_when_no_price_history(db):
    assert strategy_signals.refresh_one("AAPL", db) is None


def test_refresh_one_upserts_and_returns_doc(db, monkeypatch):
    db[PRICE_HISTORY].insert_one({"ticker": "AAPL"})
    monkeypatch.setattr(strategy_signals, "get_price_history", _empty_price_data)

    doc = strategy_signals.refresh_one("aapl", db)

    assert doc["ticker"] == "AAPL"
    assert db[STRATEGY_SIGNALS].find_one({"ticker": "AAPL"}) is not None


def test_run_strategy_signals_refresh_is_the_admin_job_entry_point(db, monkeypatch):
    db[PRICE_HISTORY].insert_one({"ticker": "AAPL"})
    monkeypatch.setattr(strategy_signals, "get_price_history", _empty_price_data)

    assert strategy_signals.run_strategy_signals_refresh(db) == 1
