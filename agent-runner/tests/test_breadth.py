"""Unit tests for tools/breadth.py — network fully faked."""
from datetime import datetime, timedelta, timezone

import mongomock
import numpy as np
import pandas as pd
import pytest

from tools import breadth
from tools.db import BREADTH_CACHE, BREADTH_UNIVERSE


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


def _records(values):
    dates = pd.date_range("2026-07-01", periods=len(values), freq="B")
    return [{"date": d.date().isoformat(), "value": v} for d, v in zip(dates, values)]


def test_detect_divergence_bullish():
    spy = pd.Series([100, 99, 98, 97, 96, 95, 94, 93, 92, 91.0],
                    index=pd.date_range("2026-07-01", periods=10, freq="B"))
    nymo = _records([-50, -60, -70, -80, -90, -55, -50, -45, -40, -35])
    assert breadth.detect_divergence(nymo, spy_close=spy)["type"] == "bullish"


def test_detect_divergence_bearish():
    spy = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109.0],
                    index=pd.date_range("2026-07-01", periods=10, freq="B"))
    nymo = _records([50, 60, 70, 80, 90, 55, 50, 45, 40, 35])
    assert breadth.detect_divergence(nymo, spy_close=spy)["type"] == "bearish"


def test_detect_divergence_none_when_confirming():
    spy = pd.Series([100, 99, 98, 97, 96, 95, 94, 93, 92, 91.0],
                    index=pd.date_range("2026-07-01", periods=10, freq="B"))
    nymo = _records([-10, -20, -30, -40, -50, -60, -70, -80, -90, -100])
    assert breadth.detect_divergence(nymo, spy_close=spy)["type"] == "none"


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
    monkeypatch.setattr(breadth, "get_universe", lambda name, db=None: [f"T{i}" for i in range(50)])
    monkeypatch.setattr(breadth, "_download_closes", lambda u, p: make_closes())
    monkeypatch.setattr(
        breadth, "detect_divergence",
        lambda recs, spy_close=None: {"type": "none", "description": "faked"},
    )

    result = breadth.get_market_breadth(lookback_days=30, db=db)

    for key in ("nymo", "namo"):
        section = result[key]
        assert len(section["history"]) == 30
        assert section["current"] == section["history"][-1]["value"]
        assert section["zone"] in {"oversold", "neutral", "overbought", "unknown"}
        assert section["trend"] in {"rising", "falling", "flat"}
    assert result["method"] == "computed_ratio_adjusted"
    assert db[BREADTH_CACHE].count_documents({"exchange": "nyse"}) == 30

    # second call same day: served from cache, no download
    monkeypatch.setattr(breadth, "_download_closes", lambda u, p: pytest.fail("should be cached"))
    again = breadth.get_market_breadth(lookback_days=30, db=db)
    assert again["nymo"]["history"] == result["nymo"]["history"]
