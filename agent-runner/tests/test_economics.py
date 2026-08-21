"""Unit tests for tools/economics.py — network fully faked.
Spec: specs/026-macro-market-dashboard/tasks.md T004
"""
from datetime import date, datetime, timezone

import mongomock
import pytest
import requests

from tools import economics
from tools.db import (
    DATASET_META,
    ECONOMIC_CALENDAR_EVENTS,
    ECONOMIC_INDICATORS,
    MARKET_RISK_PREMIUM,
    TREASURY_RATES,
)


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


def treasury_row(d: str, **maturities) -> dict:
    row = {"date": d}
    row.update(maturities)
    return row


# --- backfill windowing (pure, no network) -----------------------------------

def test_backfill_windows_are_non_overlapping_and_span_two_years():
    today = date(2026, 8, 21)
    windows = economics._backfill_windows(today=today)

    assert windows[0][0] == today - __import__("datetime").timedelta(days=730)
    assert windows[-1][1] == today
    for (s1, e1), (s2, _e2) in zip(windows, windows[1:]):
        assert e1 < s2  # non-overlapping, strictly increasing
    for start, end in windows:
        assert (end - start).days <= 90


def test_backfill_windows_default_today_when_unset():
    windows = economics._backfill_windows()
    assert windows[-1][1] == datetime.now(timezone.utc).date()


# --- treasury rates: backfill path -------------------------------------------

def test_treasury_backfill_calls_once_per_window_and_stores_rows(db, monkeypatch):
    calls = []

    def fake_fmp_get(path, db=None):
        calls.append(path)
        return [treasury_row("2026-08-01", year10=4.5, year2=4.1)]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)

    count = economics.pull_treasury_rates(db)

    expected_windows = len(economics._backfill_windows())
    assert len(calls) == expected_windows
    assert count == expected_windows  # one stored row per window in this fake
    assert db[DATASET_META].find_one({"dataset": economics.BACKFILL_DATASET})["last_run_status"] == "success"


def test_treasury_backfill_maps_maturities_and_skips_nulls(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        return [
            treasury_row("2026-08-19", month1=3.77, year10=4.65, year30=5.19),
            treasury_row("2026-08-18"),  # every maturity absent -> dropped
        ]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)
    economics.pull_treasury_rates(db)

    stored = db[TREASURY_RATES].find_one({"date": "2026-08-19"})
    assert stored["m1"] == 3.77
    assert stored["y10"] == 4.65
    assert stored["y30"] == 5.19
    assert stored["m2"] is None  # absent maturity -> None, never 0
    assert db[TREASURY_RATES].find_one({"date": "2026-08-18"}) is None


def test_treasury_backfill_does_not_repeat_once_marker_exists(db, monkeypatch):
    calls = []

    def fake_fmp_get(path, db=None):
        calls.append(path)
        return [treasury_row("2026-08-19", year10=4.65)]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)
    economics.pull_treasury_rates(db)  # backfill: many calls
    calls.clear()

    economics.pull_treasury_rates(db)  # incremental: exactly one call
    assert len(calls) == 1


def test_treasury_incremental_resumes_from_last_stored_session(db, monkeypatch):
    db[TREASURY_RATES].insert_one({"date": "2026-08-10", "y10": 4.5, "source": "fmp"})
    from tools.db import write_dataset_meta
    write_dataset_meta(economics.BACKFILL_DATASET, "success", 1, db=db)

    seen_paths = []

    def fake_fmp_get(path, db=None):
        seen_paths.append(path)
        return [treasury_row("2026-08-19", year10=4.65)]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)
    economics.pull_treasury_rates(db)

    assert len(seen_paths) == 1
    assert "from=2026-08-10" in seen_paths[0]  # resumes from last stored session, not "yesterday"


# --- economic calendar --------------------------------------------------------

def calendar_row(**overrides) -> dict:
    row = {
        "date": "2026-08-25 12:30:00", "country": "US", "event": "Retail Sales MoM",
        "impact": "High", "previous": 0.4, "estimate": 0.3, "actual": None, "unit": "%",
    }
    row.update(overrides)
    return row


def test_calendar_pull_keeps_only_us_high_or_medium_impact(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        return [
            calendar_row(event="US High", impact="High"),
            calendar_row(event="US Medium", impact="Medium"),
            calendar_row(event="US Low", impact="Low"),
            calendar_row(event="JP High", country="JP", impact="High"),
        ]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)
    count = economics.pull_economic_calendar(db)

    assert count == 2
    stored_events = {d["event"] for d in db[ECONOMIC_CALENDAR_EVENTS].find({})}
    assert stored_events == {"US High", "US Medium"}


def test_calendar_pull_prunes_rows_outside_the_window(db, monkeypatch):
    stale = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db[ECONOMIC_CALENDAR_EVENTS].insert_one(
        {"date": stale, "event": "Ancient Release", "country": "US", "impact": "High"}
    )

    monkeypatch.setattr(economics, "fmp_get", lambda path, db=None: [])
    economics.pull_economic_calendar(db)

    assert db[ECONOMIC_CALENDAR_EVENTS].find_one({"event": "Ancient Release"}) is None


def test_calendar_pull_upserts_on_date_and_event(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        return [calendar_row(actual=None)]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)
    economics.pull_economic_calendar(db)
    assert db[ECONOMIC_CALENDAR_EVENTS].count_documents({}) == 1

    def fake_fmp_get_reported(path, db=None):
        return [calendar_row(actual=0.6)]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get_reported)
    economics.pull_economic_calendar(db)

    assert db[ECONOMIC_CALENDAR_EVENTS].count_documents({}) == 1  # upsert, not duplicate
    assert db[ECONOMIC_CALENDAR_EVENTS].find_one({})["actual"] == 0.6


# --- economic indicators -------------------------------------------------------

def test_indicators_pull_accumulates_readings_across_runs(db, monkeypatch):
    responses = iter([
        [{"name": "GDP", "date": "2025-10-01", "value": 31422.5}],
        [{"name": "GDP", "date": "2026-01-01", "value": 31600.0}],
    ])

    def fake_fmp_get(path, db=None):
        if "name=GDP" in path:
            return next(responses)
        return []

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)
    economics.pull_economic_indicators(db)
    economics.pull_economic_indicators(db)

    gdp_readings = list(db[ECONOMIC_INDICATORS].find({"indicator": "GDP"}))
    assert len(gdp_readings) == 2  # second run's reading accumulates, doesn't overwrite the first


def test_indicators_pull_skips_a_failing_series_without_aborting_others(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        if "name=GDP" in path:
            raise requests.exceptions.ConnectionError("boom")
        return [{"name": "x", "date": "2025-11-19", "value": 2.27}]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)
    count = economics.pull_economic_indicators(db)

    assert db[ECONOMIC_INDICATORS].find_one({"indicator": "GDP"}) is None
    assert count == len(economics.INDICATOR_SERIES) - 1  # every other series still landed


# --- market risk premium -------------------------------------------------------

def test_risk_premium_keeps_only_the_us_row(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        return [
            {"country": "Zimbabwe", "countryRiskPremium": 11.66, "totalEquityRiskPremium": 15.89},
            {"country": "United States", "countryRiskPremium": 0.23, "totalEquityRiskPremium": 4.46},
        ]

    monkeypatch.setattr(economics, "fmp_get", fake_fmp_get)
    count = economics.pull_market_risk_premium(db)

    assert count == 1
    assert db[MARKET_RISK_PREMIUM].count_documents({}) == 1
    stored = db[MARKET_RISK_PREMIUM].find_one({})
    assert stored["country"] == "United States"
    assert stored["total_equity_risk_premium"] == 4.46


# --- orchestrator + fail-soft ---------------------------------------------------

def test_run_economics_pull_writes_a_single_dataset_meta_on_success(db, monkeypatch):
    monkeypatch.setattr(economics, "pull_treasury_rates", lambda db: 5)
    monkeypatch.setattr(economics, "pull_economic_calendar", lambda db: 3)
    monkeypatch.setattr(economics, "pull_economic_indicators", lambda db: 6)
    monkeypatch.setattr(economics, "pull_market_risk_premium", lambda db: 1)

    total = economics.run_economics_pull(db)

    assert total == 15
    meta = db[DATASET_META].find_one({"dataset": "economics"})
    assert meta["last_run_status"] == "success"
    assert meta["record_count"] == 15


def test_run_economics_pull_fail_soft_leaves_last_success_at_untouched(db, monkeypatch):
    monkeypatch.setattr(economics, "pull_treasury_rates", lambda db: 5)
    monkeypatch.setattr(economics, "pull_economic_calendar", lambda db: 3)
    monkeypatch.setattr(economics, "pull_economic_indicators", lambda db: 6)
    monkeypatch.setattr(economics, "pull_market_risk_premium", lambda db: 1)
    economics.run_economics_pull(db)
    first_success_at = db[DATASET_META].find_one({"dataset": "economics"})["last_success_at"]

    db[TREASURY_RATES].insert_one({"date": "2026-08-19", "y10": 4.65, "source": "fmp"})

    def always_fails(db):
        raise requests.exceptions.ConnectionError("provider down")

    monkeypatch.setattr(economics, "pull_treasury_rates", always_fails)
    monkeypatch.setattr(economics, "pull_economic_calendar", always_fails)
    monkeypatch.setattr(economics, "pull_economic_indicators", always_fails)
    monkeypatch.setattr(economics, "pull_market_risk_premium", always_fails)

    economics.run_economics_pull(db)

    meta = db[DATASET_META].find_one({"dataset": "economics"})
    assert meta["last_run_status"] == "failed"
    assert meta["last_success_at"] == first_success_at  # never regresses on failure
    assert db[TREASURY_RATES].find_one({"date": "2026-08-19"}) is not None  # prior data intact
