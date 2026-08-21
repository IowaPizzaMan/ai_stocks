"""Price store: merge, coverage, and delta-window logic.
Spec: specs/024-delta-data-pulls (US2); contracts/price-store.md.

⚠️  The CASES table and the pure-function tests below are duplicated verbatim in
backend/tests/test_price_store.py. That duplication IS the cross-container
consistency check (constitution Principle VI, research D4) — the two services
cannot share a package, so divergence has to fail a test instead of silently
corrupting stored data. Change one, change both.
"""
from datetime import date, timedelta

import mongomock
import pandas as pd
import pytest

from tools import price_store
from tools.db import PRICE_HISTORY


def bar(d, close=100.0):
    return {"date": d, "open": close - 1, "high": close + 1, "low": close - 2,
            "close": close, "volume": 1000}


# --- merge_bars -----------------------------------------------------------------
# (case table — keep byte-identical with backend/tests/test_price_store.py)

def test_merge_into_empty_baseline_returns_fetched_sorted():
    fetched = [bar("2026-01-03"), bar("2026-01-01"), bar("2026-01-02")]
    merged = price_store.merge_bars([], fetched)
    assert [b["date"] for b in merged] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_merge_appends_new_bars_after_stored():
    stored = [bar("2026-01-01"), bar("2026-01-02")]
    merged = price_store.merge_bars(stored, [bar("2026-01-03")])
    assert [b["date"] for b in merged] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_merge_with_empty_fetch_is_a_noop():
    """A pull on a weekend or holiday yields nothing new — normal, not a failure,
    and it must not disturb the stored series."""
    stored = [bar("2026-01-01"), bar("2026-01-02")]
    assert price_store.merge_bars(stored, []) == stored


def test_merge_deduplicates_the_overlap_day():
    """delta_start deliberately re-requests the newest stored day (research D5),
    so the merge has to absorb that overlap without duplicating it."""
    stored = [bar("2026-01-01"), bar("2026-01-02", close=200.0)]
    fetched = [bar("2026-01-02", close=200.0), bar("2026-01-03")]
    merged = price_store.merge_bars(stored, fetched)
    assert [b["date"] for b in merged] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_fetched_bar_wins_on_a_date_collision():
    """A re-fetched bar is a correction (split/dividend re-adjustment), so the
    provider's version replaces ours rather than being discarded."""
    stored = [bar("2026-01-02", close=200.0)]
    fetched = [bar("2026-01-02", close=100.0)]
    merged = price_store.merge_bars(stored, fetched)
    assert len(merged) == 1
    assert merged[0]["close"] == 100.0


def test_merge_fills_a_mid_series_gap():
    stored = [bar("2026-01-01"), bar("2026-01-05")]
    fetched = [bar("2026-01-02"), bar("2026-01-03")]
    merged = price_store.merge_bars(stored, fetched)
    assert [b["date"] for b in merged] == [
        "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-05"]


def test_merge_sorts_out_of_order_input():
    merged = price_store.merge_bars(
        [bar("2026-01-05"), bar("2026-01-01")],
        [bar("2026-01-03")],
    )
    assert [b["date"] for b in merged] == ["2026-01-01", "2026-01-03", "2026-01-05"]


def test_merge_never_mutates_its_arguments():
    stored = [bar("2026-01-01")]
    fetched = [bar("2026-01-02")]
    price_store.merge_bars(stored, fetched)
    assert len(stored) == 1 and len(fetched) == 1


def test_merge_drops_bars_with_no_date():
    merged = price_store.merge_bars([], [bar("2026-01-01"), {"close": 5.0}])
    assert [b["date"] for b in merged] == ["2026-01-01"]


# --- delta_start ----------------------------------------------------------------

TODAY = date(2026, 8, 17)


def test_delta_start_without_coverage_requests_full():
    assert price_store.delta_start(None, TODAY) is None
    assert price_store.delta_start({}, TODAY) is None
    assert price_store.delta_start({"last_date": None}, TODAY) is None


def test_delta_start_backs_off_one_day_never_forward():
    """The whole point of this function. Starting at last_date + 1 silently drops
    a trading day whenever the provider's day boundary and our stored date
    disagree; one re-requested day costs a single row (research D5)."""
    start = price_store.delta_start({"last_date": "2026-08-15"}, TODAY)
    assert start == date(2026, 8, 14)


def test_delta_start_falls_back_to_full_when_the_gap_is_too_wide():
    """FR-011 — past the point where the delta window rivals the useful history
    length, a clean full fetch is simpler and costs the same one request."""
    stale = (TODAY - timedelta(days=800)).isoformat()
    assert price_store.delta_start({"last_date": stale}, TODAY) is None


def test_delta_start_still_incremental_just_inside_the_gap_limit():
    inside = (TODAY - timedelta(days=700)).isoformat()
    assert price_store.delta_start({"last_date": inside}, TODAY) is not None


def test_delta_start_tolerates_an_unparseable_stored_date():
    assert price_store.delta_start({"last_date": "not-a-date"}, TODAY) is None


# --- build_coverage --------------------------------------------------------------

def test_build_coverage_derives_bounds_from_the_bars():
    bars = [bar("2026-01-01"), bar("2026-01-02"), bar("2026-01-03")]
    cov = price_store.build_coverage(bars, None, "full")
    assert cov["first_date"] == "2026-01-01"
    assert cov["last_date"] == "2026-01-03"
    assert cov["bar_count"] == 3


def test_full_build_sets_both_timestamps():
    cov = price_store.build_coverage([bar("2026-01-01")], None, "full")
    assert cov["established_at"] is not None
    assert cov["extended_at"] is not None


def test_delta_advances_extended_but_preserves_established():
    """FR-010 — nothing re-establishes on a schedule, so established_at is the
    honest record of when this series was last built from scratch."""
    first = price_store.build_coverage([bar("2026-01-01")], None, "full")
    later = price_store.build_coverage(
        [bar("2026-01-01"), bar("2026-01-02")], first, "delta")

    assert later["established_at"] == first["established_at"]
    assert later["extended_at"] >= first["extended_at"]
    assert later["bar_count"] == 2


def test_build_coverage_on_empty_bars_is_safe():
    cov = price_store.build_coverage([], None, "full")
    assert cov["bar_count"] == 0
    assert cov["first_date"] is None and cov["last_date"] is None


# --- get_series (I/O) -------------------------------------------------------------

@pytest.fixture
def db():
    return mongomock.MongoClient()["price_store_test"]


def frame(dates, close=100.0):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates], name="Date")
    return pd.DataFrame(
        {"Open": close - 1, "High": close + 1, "Low": close - 2,
         "Close": close, "Volume": 1000},
        index=idx,
    )


def seed(db, ticker, dates):
    bars = [bar(d) for d in dates]
    db[PRICE_HISTORY].insert_one({
        "ticker": ticker,
        "bars": bars,
        "coverage": price_store.build_coverage(bars, None, "full"),
    })


def test_refresh_none_never_contacts_the_provider(db, monkeypatch):
    """FR-014 / SC-003 — the store IS the in-pull deduplication. Later readers
    in the same pull must not be able to trigger a second download."""
    seed(db, "AAPL", ["2026-01-01", "2026-01-02"])
    monkeypatch.setattr(price_store, "_fetch", lambda *a, **k: pytest.fail("fetched"))

    df, meta = price_store.get_series("AAPL", refresh="none", db=db)
    assert len(df) == 2
    assert meta["requests"] == 0
    assert meta["retrieval"] == "stored"


def test_cold_ticker_falls_back_to_a_full_fetch(db, monkeypatch):
    calls = []

    def fake_fetch(ticker, start, db=None):
        calls.append(start)
        return frame(["2026-01-01", "2026-01-02"])

    monkeypatch.setattr(price_store, "_fetch", fake_fetch)
    df, meta = price_store.get_series("AAPL", refresh="delta", db=db)

    assert calls == [None]                     # FR-007 — no baseline, fetch all
    assert meta["retrieval"] == "full"
    assert len(df) == 2


def test_delta_requests_only_from_the_overlap_day(db, monkeypatch):
    seed(db, "AAPL", ["2026-01-01", "2026-01-02"])
    calls = []

    def fake_fetch(ticker, start, db=None):
        calls.append(start)
        return frame(["2026-01-03"])

    monkeypatch.setattr(price_store, "_fetch", fake_fetch)
    df, meta = price_store.get_series("AAPL", refresh="delta", db=db)

    assert calls == [date(2026, 1, 1)]         # last_date 01-02 minus one day
    assert meta["retrieval"] == "incremental"
    assert len(df) == 3                        # extended, not replaced


def test_full_refresh_replaces_the_stored_series(db, monkeypatch):
    """FR-025 — a full refresh establishes a new baseline rather than merging
    into the one the operator has just declared suspect."""
    seed(db, "AAPL", ["2026-01-01", "2026-01-02"])
    db[PRICE_HISTORY].update_one({"ticker": "AAPL"}, {"$set": {"bars.0.close": 99999}})

    monkeypatch.setattr(price_store, "_fetch",
                        lambda t, s, db=None: frame(["2026-01-01", "2026-01-02"]))
    df, meta = price_store.get_series("AAPL", refresh="full", db=db)

    assert meta["retrieval"] == "full"
    doc = db[PRICE_HISTORY].find_one({"ticker": "AAPL"})
    assert all(b["close"] == 100.0 for b in doc["bars"])   # corruption gone


def test_fetch_failure_serves_stored_bars_and_degrades(db, monkeypatch):
    """FR-012 / FR-030 — a failed refresh must leave the stored series intact and
    the pull must still complete."""
    seed(db, "AAPL", ["2026-01-01", "2026-01-02"])

    def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(price_store, "_fetch", boom)
    df, meta = price_store.get_series("AAPL", refresh="delta", db=db)

    assert len(df) == 2
    assert meta["outcome"] == "degraded"
    doc = db[PRICE_HISTORY].find_one({"ticker": "AAPL"})
    assert len(doc["bars"]) == 2


def test_budget_exceeded_serves_stored_bars_and_degrades(db, monkeypatch):
    """FR-027 — a blown daily cap degrades, it never fails the pull."""
    from tools.fmp_client import FmpBudgetExceededError
    seed(db, "AAPL", ["2026-01-01"])

    def capped(*a, **k):
        raise FmpBudgetExceededError("cap")

    monkeypatch.setattr(price_store, "_fetch", capped)
    df, meta = price_store.get_series("AAPL", refresh="delta", db=db)

    assert len(df) == 1
    assert meta["outcome"] == "degraded"


def test_interrupted_full_refresh_leaves_the_previous_series_intact(db, monkeypatch):
    """SC-013 / FR-030 — the new series is built fully in memory before a single
    atomic swap, so an interruption cannot leave a truncated or empty series."""
    seed(db, "AAPL", ["2026-01-01", "2026-01-02", "2026-01-03"])
    before = db[PRICE_HISTORY].find_one({"ticker": "AAPL"})

    def die_midway(*a, **k):
        raise KeyboardInterrupt("worker restarted")

    monkeypatch.setattr(price_store, "_fetch", die_midway)
    with pytest.raises(KeyboardInterrupt):
        price_store.get_series("AAPL", refresh="full", db=db)

    after = db[PRICE_HISTORY].find_one({"ticker": "AAPL"})
    assert len(after["bars"]) == len(before["bars"]) == 3
    assert after["coverage"]["established_at"] == before["coverage"]["established_at"]


def test_empty_fetch_result_does_not_wipe_stored_bars(db, monkeypatch):
    """A provider that answers 200 with nothing must not be read as 'this ticker
    has no history'."""
    seed(db, "AAPL", ["2026-01-01", "2026-01-02"])
    monkeypatch.setattr(price_store, "_fetch", lambda t, s, db=None: frame([]))

    df, _ = price_store.get_series("AAPL", refresh="delta", db=db)
    assert len(df) == 2


def test_returned_frame_matches_the_legacy_fetch_shape(db, monkeypatch):
    """FR-020 — downstream resampling and indicators are untouched by this
    feature, which only holds if the frame shape is identical to before."""
    seed(db, "AAPL", ["2026-01-01", "2026-01-02"])
    df, _ = price_store.get_series("AAPL", refresh="none", db=db)

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.index.name == "Date"
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing


def test_cold_ticker_with_no_data_anywhere_returns_empty_frame(db, monkeypatch):
    monkeypatch.setattr(price_store, "_fetch", lambda t, s, db=None: frame([]))
    df, meta = price_store.get_series("ZZZZ", refresh="delta", db=db)
    assert df.empty
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
