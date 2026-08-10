"""Unit tests for tools/breadth.py — network fully faked."""
from datetime import datetime, timedelta, timezone

import mongomock
import numpy as np
import pandas as pd
import pytest

from tools import breadth
from tools.db import BREADTH_CACHE, BREADTH_DIVERGENCES, BREADTH_UNIVERSE, MARKET_FLOW_EVENTS


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


def make_closes(rows=150, cols=50, seed=3):
    rng = np.random.default_rng(seed)
    data = 100 + np.cumsum(rng.normal(0, 1, (rows, cols)), axis=0)
    idx = pd.date_range("2026-01-01", periods=rows, freq="B")
    return pd.DataFrame(data, index=idx, columns=[f"T{i}" for i in range(cols)])


# --- math --------------------------------------------------------------------

def test_compute_mcclellan_columns_and_bounds():
    df = breadth.compute_mcclellan(make_closes())
    assert {"advancers", "decliners", "rana", "mcclellan"} <= set(df.columns)
    # RANA is bounded by ±1000 by construction; MO is a difference of its EMAs
    assert df["rana"].between(-1000, 1000).all()
    assert (df["advancers"] + df["decliners"] <= 50).all()
    assert df["mcclellan"].notna().all()


def test_compute_mcclellan_all_advancing():
    closes = pd.DataFrame(
        np.arange(1, 61).reshape(60, 1) + np.zeros((60, 10)),
        index=pd.date_range("2026-01-01", periods=60, freq="B"),
        columns=[f"T{i}" for i in range(10)],
    )
    df = breadth.compute_mcclellan(closes)
    assert (df["rana"] == 1000).all()
    # both EMAs converge to 1000 → MO approaches 0 from above
    assert df["mcclellan"].iloc[-1] >= 0


# --- interpretation ----------------------------------------------------------

def test_classify_zone():
    assert breadth.classify_zone(None) == "unknown"
    assert breadth.classify_zone(-75) == "oversold"
    assert breadth.classify_zone(75) == "overbought"
    assert breadth.classify_zone(0) == "neutral"


def test_compute_trend():
    up = [{"value": v} for v in [0, 5, 10, 15, 20]]
    down = [{"value": v} for v in [20, 10, 5, 0, -10]]
    flat = [{"value": v} for v in [0, 1, -1, 2, 1]]
    assert breadth.compute_trend(up) == "rising"
    assert breadth.compute_trend(down) == "falling"
    assert breadth.compute_trend(flat) == "flat"
    assert breadth.compute_trend([]) == "flat"


def _dates(n, start="2026-07-01"):
    return [d.date().isoformat() for d in pd.date_range(start, periods=n, freq="B")]


def _records(values, start="2026-07-01"):
    return [{"date": d, "value": v} for d, v in zip(_dates(len(values), start), values)]


def _spy(closes, start="2026-07-01"):
    return [{"date": d, "close": c} for d, c in zip(_dates(len(closes), start), closes)]


def test_detect_divergence_bullish():
    spy = _spy([100, 99, 98, 97, 96, 95, 94, 93, 92, 91.0])
    nymo = _records([-50, -60, -70, -80, -90, -55, -50, -45, -40, -35])
    out = breadth.detect_divergence(nymo, spy)
    assert out["type"] == "bullish"
    # anchors: SPY's two swing lows, NYMO's two swing lows (the higher retest)
    assert [p["value"] for p in out["price_points"]] == [96, 91]
    assert [p["value"] for p in out["osc_points"]] == [-90, -55]
    assert [p["date"] for p in out["price_points"]] == ["2026-07-07", "2026-07-14"]


def test_detect_divergence_bearish():
    spy = _spy([100, 101, 102, 103, 104, 105, 106, 107, 108, 109.0])
    nymo = _records([50, 60, 70, 80, 90, 55, 50, 45, 40, 35])
    out = breadth.detect_divergence(nymo, spy)
    assert out["type"] == "bearish"
    assert [p["value"] for p in out["price_points"]] == [104, 109]
    assert [p["value"] for p in out["osc_points"]] == [90, 55]


def test_detect_divergence_none_when_confirming():
    spy = _spy([100, 99, 98, 97, 96, 95, 94, 93, 92, 91.0])
    nymo = _records([-10, -20, -30, -40, -50, -60, -70, -80, -90, -100])
    out = breadth.detect_divergence(nymo, spy)
    assert out["type"] == "none"
    assert out["price_points"] == [] and out["osc_points"] == []


def test_detect_divergence_needs_overlapping_dates():
    # NYMO and SPY series that never share a date can't be compared
    nymo = _records([-50, -60, -70, -80, -90, -55, -50, -45, -40, -35])
    spy = _spy([100, 99, 98, 97, 96, 95, 94, 93, 92, 91.0], start="2027-01-01")
    assert breadth.detect_divergence(nymo, spy)["type"] == "none"


# --- SPY caching -------------------------------------------------------------

def test_spy_records_backfills_cache_then_serves_from_it(db, monkeypatch):
    dates = _dates(3)
    for d in dates:
        db[BREADTH_CACHE].insert_one({"exchange": "nyse", "date": d, "mcclellan": 0.0})

    closes = pd.Series([500.0, 505.0, 510.0], index=pd.to_datetime(dates))
    monkeypatch.setattr(breadth, "_download_spy", lambda period: closes)
    assert breadth._spy_records(dates, db) == [
        {"date": dates[0], "close": 500.0},
        {"date": dates[1], "close": 505.0},
        {"date": dates[2], "close": 510.0},
    ]
    assert db[BREADTH_CACHE].find_one({"date": dates[1]})["spy_close"] == 505.0

    monkeypatch.setattr(breadth, "_download_spy", lambda period: pytest.fail("should be cached"))
    assert len(breadth._spy_records(dates, db)) == 3


# --- divergence history + feed events ----------------------------------------

def _bullish():
    return {"type": "bullish", "description": "d",
            "price_points": [{"date": "2026-07-01", "value": 96.0},
                             {"date": "2026-07-08", "value": 91.0}],
            "osc_points": [{"date": "2026-07-02", "value": -90.0},
                           {"date": "2026-07-09", "value": -55.0}]}


def test_divergence_tracking_emits_once_then_resolves(db):
    event = breadth.update_divergence_tracking(db, _bullish(), [], today="2026-07-10")
    assert event["divergence_type"] == "bullish"
    assert db[MARKET_FLOW_EVENTS].count_documents({}) == 1

    # same divergence still in force the next day — no second card
    assert breadth.update_divergence_tracking(db, _bullish(), [], today="2026-07-11") is None
    assert db[MARKET_FLOW_EVENTS].count_documents({}) == 1
    assert breadth.get_divergence_history(db) == []  # still open, not history yet

    none = {"type": "none", "description": "gone", "price_points": [], "osc_points": []}
    assert breadth.update_divergence_tracking(db, none, [], today="2026-07-14") is None
    history = breadth.get_divergence_history(db)
    assert len(history) == 1
    assert history[0]["type"] == "bullish"
    assert history[0]["resolved"] == "2026-07-14"
    assert history[0]["anchor_dates"] == ["2026-07-01", "2026-07-08"]


def test_divergence_flip_resolves_old_and_opens_new(db):
    breadth.update_divergence_tracking(db, _bullish(), [], today="2026-07-10")
    bearish = {**_bullish(), "type": "bearish"}
    event = breadth.update_divergence_tracking(db, bearish, [], today="2026-07-15")

    assert event["divergence_type"] == "bearish"
    assert [h["type"] for h in breadth.get_divergence_history(db)] == ["bullish"]
    assert db[BREADTH_DIVERGENCES].count_documents({"resolved": None}) == 1


def test_forward_returns_backfill_after_resolution(db):
    spy = _spy([100.0] * 5 + [110.0] * 10, start="2026-07-01")
    resolved_on = spy[4]["date"]
    breadth.update_divergence_tracking(db, _bullish(), spy, today="2026-07-01")
    none = {"type": "none", "description": "gone", "price_points": [], "osc_points": []}
    breadth.update_divergence_tracking(db, none, spy, today=resolved_on)

    # sessions after the resolution date have printed, so the follow-through fills in
    breadth.update_divergence_tracking(db, none, spy, today="2026-07-30")
    entry = breadth.get_divergence_history(db)[0]
    assert entry["spy_change_5d"] == 10.0
    assert entry["spy_change_10d"] == 10.0


def test_forward_returns_stay_none_until_sessions_print(db):
    spy = _spy([100.0] * 6, start="2026-07-01")
    breadth.update_divergence_tracking(db, _bullish(), spy, today="2026-07-01")
    none = {"type": "none", "description": "gone", "price_points": [], "osc_points": []}
    breadth.update_divergence_tracking(db, none, spy, today=spy[-1]["date"])
    entry = breadth.get_divergence_history(db)[0]
    assert entry["spy_change_5d"] is None and entry["spy_change_10d"] is None


# --- universe caching --------------------------------------------------------

def test_get_universe_prefers_fmp_and_caches(db, monkeypatch):
    monkeypatch.setattr(breadth, "_fmp_constituents", lambda name: ["AAPL", "BRK.B", "msft"])
    tickers = breadth.get_universe("sp500", db=db)
    assert tickers == ["AAPL", "BRK-B", "MSFT"]

    # cached now — a second call must not refetch
    monkeypatch.setattr(breadth, "_fmp_constituents", lambda name: pytest.fail("should be cached"))
    assert breadth.get_universe("sp500", db=db) == ["AAPL", "BRK-B", "MSFT"]


def test_get_universe_falls_back_to_scrape(db, monkeypatch):
    def boom(name):
        raise RuntimeError("fmp down")

    monkeypatch.setattr(breadth, "_fmp_constituents", boom)
    monkeypatch.setattr(breadth, "_wikipedia_sp500", lambda: ["AAA", "BBB.A"])
    assert breadth.get_universe("sp500", db=db) == ["AAA", "BBB-A"]


def test_get_universe_stale_cache_refreshes(db, monkeypatch):
    stale = datetime.now(timezone.utc) - timedelta(days=breadth.UNIVERSE_MAX_AGE_DAYS + 1)
    db[BREADTH_UNIVERSE].insert_one({"name": "sp500", "tickers": ["OLD"], "fetched_at": stale})
    monkeypatch.setattr(breadth, "_fmp_constituents", lambda name: ["NEW"])
    assert breadth.get_universe("sp500", db=db) == ["NEW"]


def test_get_universe_rejects_unknown_name(db):
    with pytest.raises(ValueError):
        breadth.get_universe("djia", db=db)


# --- end-to-end with cache ---------------------------------------------------

def test_get_market_breadth_shape_and_cache_write(db, monkeypatch):
    closes = make_closes()
    monkeypatch.setattr(breadth, "get_universe", lambda name, db=None: [f"T{i}" for i in range(50)])
    monkeypatch.setattr(breadth, "_download_closes", lambda u, p: closes)
    monkeypatch.setattr(breadth, "_download_spy", lambda period: closes["T0"])

    result = breadth.get_market_breadth(lookback_days=30, db=db)
    assert len(result["spy"]) == 30
    assert result["divergence"]["type"] in {"bullish", "bearish", "none"}
    assert result["divergence_history"] == []

    for key in ("nymo", "namo"):
        section = result[key]
        assert len(section["history"]) == 30
        assert section["current"] == section["history"][-1]["value"]
        assert section["zone"] in {"oversold", "neutral", "overbought", "unknown"}
        assert section["trend"] in {"rising", "falling", "flat"}
    assert result["method"] == "computed_ratio_adjusted"
    assert db[BREADTH_CACHE].count_documents({"exchange": "nyse"}) == 30

    # second call same day: served from cache, no download of either series
    monkeypatch.setattr(breadth, "_download_closes", lambda u, p: pytest.fail("should be cached"))
    monkeypatch.setattr(breadth, "_download_spy", lambda period: pytest.fail("should be cached"))
    again = breadth.get_market_breadth(lookback_days=30, db=db)
    assert again["nymo"]["history"] == result["nymo"]["history"]
    assert again["spy"] == result["spy"]


def test_get_market_breadth_degrades_when_spy_unavailable(db, monkeypatch):
    def boom(period):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(breadth, "get_universe", lambda name, db=None: [f"T{i}" for i in range(50)])
    monkeypatch.setattr(breadth, "_download_closes", lambda u, p: make_closes())
    monkeypatch.setattr(breadth, "_download_spy", boom)

    result = breadth.get_market_breadth(lookback_days=30, db=db)
    assert result["spy"] == []
    assert result["divergence"]["type"] == "none"
    assert len(result["nymo"]["history"]) == 30  # breadth itself still works
