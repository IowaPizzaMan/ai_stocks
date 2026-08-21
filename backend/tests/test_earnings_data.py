"""Direct unit tests for earnings_data.py's FMP-sourced history fetch (the
router-level tests in test_earnings.py mock this module out entirely)."""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
import requests

import earnings_data as ed
from fmp import FmpBudgetExceededError


def make_closes() -> pd.Series:
    idx = pd.to_datetime(["2026-07-27", "2026-07-28", "2026-07-29",
                          "2026-07-30", "2026-07-31"])
    return pd.Series([100.0, 102.0, 110.0, 111.0, 100.0], index=idx)


def test_reaction_move_bmo_prices_report_day():
    assert ed._reaction_move(make_closes(), "2026-07-29", True) == pytest.approx(7.84, abs=0.01)


def test_reaction_move_amc_prices_next_session():
    assert ed._reaction_move(make_closes(), "2026-07-28", False) == pytest.approx(7.84, abs=0.01)


def test_reaction_move_outside_history_is_none():
    assert ed._reaction_move(make_closes(), "2026-07-31", False) is None


FAKE_EARNINGS = [
    {"symbol": "BIGCO", "date": "2026-07-28", "epsEstimated": 1.5, "epsActual": 1.8, "time": "amc"},
    {"symbol": "BIGCO", "date": "2026-04-28", "epsEstimated": 1.0, "epsActual": 0.9, "time": "amc"},
]


def _fake_closes() -> pd.Series:
    base = pd.bdate_range("2026-04-01", "2026-07-31")
    closes = pd.Series(100.0, index=base)
    closes.loc["2026-07-29":] = 107.84
    closes.loc["2026-04-29":"2026-07-28"] = 95.0
    return closes


def test_earnings_history_end_to_end(db, monkeypatch):
    monkeypatch.setattr(ed, "_fmp_get", lambda path: FAKE_EARNINGS)
    monkeypatch.setattr(ed, "_fetch_eod_closes", lambda ticker: _fake_closes())

    out = ed.get_earnings_history("bigco", db)
    assert out["ticker"] == "BIGCO"
    assert out["num_quarters"] == 2
    july, april = out["quarters"]
    assert july["beat"] is True and july["surprise_pct"] == 20.0
    assert april["beat"] is False

    # cached — second call must not hit _fmp_get again
    monkeypatch.setattr(ed, "_fmp_get", lambda path: pytest.fail("should be cached"))
    again = ed.get_earnings_history("BIGCO", db)
    assert again == out


def test_earnings_history_degrades_to_empty(db, monkeypatch):
    def _raise(path):
        raise RuntimeError("fmp hiccup")

    monkeypatch.setattr(ed, "_fmp_get", _raise)
    out = ed.get_earnings_history("XYZ", db)
    assert out["quarters"] == [] and out["num_quarters"] == 0


# --- _surprise_pct (spec FR-009/FR-010/FR-011, data-model.md ss4) --------------------

def test_surprise_normal_beat():
    assert ed._surprise_pct(1.20, 1.00) == 20.0


def test_surprise_normal_miss():
    assert ed._surprise_pct(0.80, 1.00) == -20.0


def test_surprise_negative_eps_beat_is_not_inverted():
    """A company losing less than feared (-0.20 actual vs -0.30 estimate) is a
    beat. Without abs(estimate) in the denominator this flips sign and reads
    as a miss — the single highest-value assertion in the suite."""
    assert ed._surprise_pct(-0.20, -0.30) == pytest.approx(33.33, abs=0.01)


def test_surprise_negative_eps_miss():
    assert ed._surprise_pct(-0.40, -0.30) == pytest.approx(-33.33, abs=0.01)


def test_surprise_zero_estimate_is_none_not_zero_or_beat():
    assert ed._surprise_pct(0.06, 0) is None


def test_surprise_missing_actual_is_none():
    assert ed._surprise_pct(None, 1.00) is None


def test_surprise_missing_estimate_is_none():
    assert ed._surprise_pct(0.06, None) is None


# --- _reporting_state (spec FR-013, data-model.md ss3) -------------------------------

TODAY = date(2026, 8, 17)


def test_reporting_state_upcoming_future_no_actuals():
    assert ed._reporting_state("2026-08-19", None, None, TODAY) == "upcoming"


def test_reporting_state_reported_when_eps_actual_present():
    assert ed._reporting_state("2026-08-14", 1.10, None, TODAY) == "reported"


def test_reporting_state_reported_when_only_revenue_actual_present():
    assert ed._reporting_state("2026-08-14", None, 5e8, TODAY) == "reported"


def test_reporting_state_awaiting_past_date_no_actuals():
    """A past report date with no actuals yet is common (201/2347 rows in a
    probed 6-day window) and must read as awaiting, never as a miss."""
    assert ed._reporting_state("2026-08-14", None, None, TODAY) == "awaiting"


def test_reporting_state_upcoming_when_date_is_today():
    assert ed._reporting_state("2026-08-17", None, None, TODAY) == "upcoming"


# --- _dedupe_calendar_rows (spec Edge Cases) ------------------------------------------

def test_dedupe_keeps_latest_last_updated():
    rows = [
        {"symbol": "DUP", "date": "2026-08-14", "lastUpdated": "2026-08-15", "epsActual": 1.0},
        {"symbol": "DUP", "date": "2026-08-14", "lastUpdated": "2026-08-17", "epsActual": 1.1},
    ]
    out = ed._dedupe_calendar_rows(rows)
    assert len(out) == 1
    assert out[0]["epsActual"] == 1.1


def test_dedupe_tie_breaks_on_later_report_date():
    rows = [
        {"symbol": "DUP", "date": "2026-08-10", "lastUpdated": "2026-08-17", "epsActual": 1.0},
        {"symbol": "DUP", "date": "2026-08-14", "lastUpdated": "2026-08-17", "epsActual": 1.1},
    ]
    out = ed._dedupe_calendar_rows(rows)
    assert len(out) == 1
    assert out[0]["date"] == "2026-08-14"


def test_dedupe_leaves_distinct_symbols_alone():
    rows = [
        {"symbol": "AAA", "date": "2026-08-14", "lastUpdated": "2026-08-17"},
        {"symbol": "BBB", "date": "2026-08-14", "lastUpdated": "2026-08-17"},
    ]
    assert len(ed._dedupe_calendar_rows(rows)) == 2


# --- _screen_and_build: screening + ordering (spec FR-019, FR-020) -------------------

UNIVERSE = {
    "BIG": {"market_cap": 50e9, "name": "Big Co", "sector": "Technology"},
    "MID": {"market_cap": 5e9, "name": "Mid Co", "sector": "Energy"},
    "SMALL": {"market_cap": 6e8, "name": "Small Co", "sector": "Industrials"},
}


def test_screen_drops_symbols_outside_universe():
    rows = [
        {"symbol": "MID", "date": "2026-08-14", "lastUpdated": "2026-08-17"},
        {"symbol": "NOCOVERAGE", "date": "2026-08-14", "lastUpdated": "2026-08-17"},
    ]
    out = ed._screen_and_build(rows, UNIVERSE, TODAY)
    assert [e["ticker"] for e in out] == ["MID"]


def test_screen_orders_by_market_cap_descending_regardless_of_date():
    rows = [
        {"symbol": "SMALL", "date": "2026-08-14", "lastUpdated": "2026-08-17"},
        {"symbol": "BIG", "date": "2026-08-19", "lastUpdated": "2026-08-17"},
        {"symbol": "MID", "date": "2026-08-10", "lastUpdated": "2026-08-17"},
    ]
    out = ed._screen_and_build(rows, UNIVERSE, TODAY)
    assert [e["ticker"] for e in out] == ["BIG", "MID", "SMALL"]


def test_screen_populates_surprise_and_state_per_row():
    rows = [
        {"symbol": "BIG", "date": "2026-08-14", "lastUpdated": "2026-08-17",
         "epsActual": 1.20, "epsEstimated": 1.00,
         "revenueActual": 11e9, "revenueEstimated": 10e9},
        {"symbol": "MID", "date": "2026-08-19", "lastUpdated": "2026-08-17",
         "epsEstimated": 0.50},
    ]
    out = ed._screen_and_build(rows, UNIVERSE, TODAY)
    reported = next(e for e in out if e["ticker"] == "BIG")
    upcoming = next(e for e in out if e["ticker"] == "MID")

    assert reported["reporting_state"] == "reported"
    assert reported["eps_surprise_pct"] == 20.0
    assert reported["beat"] is True

    assert upcoming["reporting_state"] == "upcoming"
    assert upcoming["eps_actual"] is None
    assert upcoming["eps_surprise_pct"] is None
    assert upcoming["beat"] is None


# --- get_earnings_calendar: caching, budget guard, degraded paths --------------------

RAW_ROWS = [
    {"symbol": "BIG", "date": "2026-08-14", "lastUpdated": "2026-08-17",
     "epsActual": 1.20, "epsEstimated": 1.00},
]


def test_calendar_fetches_screens_and_caches(db, monkeypatch):
    monkeypatch.setattr(ed, "fmp_get", lambda path, db: RAW_ROWS)
    monkeypatch.setattr(ed, "get_screener_universe", lambda db: UNIVERSE)

    out = ed.get_earnings_calendar(date(2026, 8, 15), date(2026, 8, 19), db)
    assert out["stale"] is False
    assert out["total_before_screen"] == 1
    assert [e["ticker"] for e in out["entries"]] == ["BIG"]

    # second call within TTL must not refetch
    monkeypatch.setattr(ed, "fmp_get",
                        lambda path, db: (_ for _ in ()).throw(AssertionError("should be cached")))
    again = ed.get_earnings_calendar(date(2026, 8, 15), date(2026, 8, 19), db)
    assert again["entries"] == out["entries"]
    assert again["stale"] is False


def test_calendar_cache_key_is_range_shaped_not_days(db, monkeypatch):
    """Must not collide with the agent-runner's {"type": "calendar", "days": N}
    docs in the same collection (constitution Principle VI, research.md D7)."""
    monkeypatch.setattr(ed, "fmp_get", lambda path, db: RAW_ROWS)
    monkeypatch.setattr(ed, "get_screener_universe", lambda db: UNIVERSE)

    ed.get_earnings_calendar(date(2026, 8, 15), date(2026, 8, 19), db)
    doc = db.earnings_cache.find_one({"type": "calendar_range"})
    assert doc is not None
    assert doc["from"] == "2026-08-15" and doc["to"] == "2026-08-19"


def test_calendar_budget_exceeded_serves_stale_cache(db, monkeypatch):
    key = {"type": "calendar_range", "from": "2026-08-15", "to": "2026-08-19"}
    db.earnings_cache.replace_one(
        key,
        {**key, "data": {"entries": [{"ticker": "OLD"}], "total_before_screen": 1},
         "fetched_at": datetime.now(timezone.utc) - timedelta(hours=10)},
        upsert=True,
    )

    def _raise(path, db):
        raise FmpBudgetExceededError("cap")

    monkeypatch.setattr(ed, "fmp_get", _raise)
    out = ed.get_earnings_calendar(date(2026, 8, 15), date(2026, 8, 19), db)
    assert out["stale"] is True
    assert out["entries"] == [{"ticker": "OLD"}]


def test_calendar_budget_exceeded_no_cache_raises(db, monkeypatch):
    def _raise(path, db):
        raise FmpBudgetExceededError("cap")

    monkeypatch.setattr(ed, "fmp_get", _raise)
    with pytest.raises(FmpBudgetExceededError):
        ed.get_earnings_calendar(date(2026, 8, 15), date(2026, 8, 19), db)


def test_calendar_provider_unreachable_no_cache_raises_typed_error(db, monkeypatch):
    def _raise(path, db):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(ed, "fmp_get", _raise)
    with pytest.raises(ed.CalendarUnavailableError):
        ed.get_earnings_calendar(date(2026, 8, 15), date(2026, 8, 19), db)


def test_calendar_universe_unavailable_raises_typed_error(db, monkeypatch):
    monkeypatch.setattr(ed, "fmp_get", lambda path, db: RAW_ROWS)

    def _raise(db):
        raise RuntimeError("nasdaq screener down")

    monkeypatch.setattr(ed, "get_screener_universe", _raise)
    with pytest.raises(ed.UniverseUnavailableError):
        ed.get_earnings_calendar(date(2026, 8, 15), date(2026, 8, 19), db)
