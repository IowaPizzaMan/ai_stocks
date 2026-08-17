"""Price endpoint tests.

Rewritten for specs/024-delta-data-pulls: the endpoint no longer fetches per
resolution into four TTL cache documents. It reads one maintained daily series
and resamples locally, so the tests that used to assert "weekly refetches at a
weekly interval" now assert the opposite — that switching resolution costs
nothing (SC-004).
"""
import pandas as pd
import pytest

import price_store
from db import PRICE_HISTORY


def daily_frame(rows=5, start="2026-07-01"):
    idx = pd.date_range(start, periods=rows, freq="B")
    return pd.DataFrame(
        {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1_000_000},
        index=idx,
    )


def climbing_frame(years: int, start="2006-01-02") -> pd.DataFrame:
    """Ascending daily bars whose close climbs by 1/day, so each resample bin's
    first/last/min/max are all predictable."""
    idx = pd.date_range(start, periods=years * 252, freq="B")
    n = len(idx)
    return pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(n)],
            "High": [101.0 + i for i in range(n)],
            "Low": [99.0 + i for i in range(n)],
            "Close": [100.5 + i for i in range(n)],
            "Volume": [1_000] * n,
        },
        index=idx,
    )


def seed_series(db, ticker, df):
    """Puts a series in the store the way a pull would have."""
    bars = price_store.frame_to_bars(df)
    db[PRICE_HISTORY].replace_one(
        {"ticker": ticker},
        {"ticker": ticker, "bars": bars,
         "coverage": price_store.build_coverage(bars, None, "full")},
        upsert=True,
    )


@pytest.fixture
def no_fetch(monkeypatch):
    """Any provider call is a test failure — these paths must be served from the
    store alone."""
    monkeypatch.setattr(price_store, "_fetch",
                        lambda *a, **k: pytest.fail("endpoint hit the provider"))


def test_price_returns_bars_from_the_stored_series(client, db, no_fetch):
    seed_series(db, "AAPL", daily_frame())

    r = client.get("/stocks/aapl/price").json()
    assert r["ticker"] == "AAPL"
    assert r["resolution"] == "daily"
    assert len(r["bars"]) == 5
    assert r["bars"][0] == {"date": "2026-07-01", "open": 100.0, "high": 101.0,
                            "low": 99.0, "close": 100.5, "volume": 1_000_000}


def test_switching_resolution_costs_zero_requests(client, db, monkeypatch):
    """SC-004 — the headline win. This used to be four full downloads per
    ticker, one per chart tab."""
    seed_series(db, "AAPL", climbing_frame(4))
    calls = []
    monkeypatch.setattr(price_store, "_fetch",
                        lambda *a, **k: calls.append(a) or daily_frame())

    for resolution in ("daily", "weekly", "monthly", "yearly", "daily"):
        assert client.get(f"/stocks/AAPL/price?resolution={resolution}").status_code == 200

    assert calls == []


def test_cold_ticker_populates_the_store_once(client, db, monkeypatch):
    """A page view for a ticker nothing has pulled yet still has to get data —
    but only once, and it must land in the store for later reads."""
    calls = []

    def fetch(ticker, start, db=None):
        calls.append((ticker, start))
        return daily_frame()

    monkeypatch.setattr(price_store, "_fetch", fetch)

    assert client.get("/stocks/NEW/price").status_code == 200
    assert len(calls) == 1
    assert calls[0][1] is None          # no baseline → full fetch (FR-007)

    # now stored: a second read must not fetch again
    assert client.get("/stocks/NEW/price?resolution=weekly").status_code == 200
    assert len(calls) == 1
    assert db[PRICE_HISTORY].find_one({"ticker": "NEW"}) is not None


def test_price_unknown_resolution_422(client):
    assert client.get("/stocks/AAPL/price?resolution=hourly").status_code == 422


def test_price_no_data_anywhere_404(client, db, monkeypatch):
    monkeypatch.setattr(price_store, "_fetch",
                        lambda *a, **k: pd.DataFrame(columns=price_store.OHLCV_COLUMNS))
    assert client.get("/stocks/GONE/price").status_code == 404


def test_price_drops_nan_bars(client, db, no_fetch):
    df = daily_frame(3)
    df.iloc[1, df.columns.get_loc("Close")] = float("nan")
    seed_series(db, "NAN", df)

    r = client.get("/stocks/NAN/price")
    assert r.status_code == 200
    bars = r.json()["bars"]
    assert len(bars) == 2
    assert [b["date"] for b in bars] == ["2026-07-01", "2026-07-03"]


# --- resampling (021 windows, now derived locally) ----------------------------

def test_yearly_resamples_per_calendar_year(client, db, no_fetch):
    seed_series(db, "YR", climbing_frame(3))

    bars = client.get("/stocks/YR/price?resolution=yearly").json()["bars"]

    years = [b["date"][:4] for b in bars]
    assert years == sorted(set(years))
    assert len(bars) == len(set(years))

    # OHLCV aggregation: open=first, high=max, low=min, close=last, volume=sum
    first_year = bars[0]
    assert first_year["open"] == 100.0
    assert first_year["low"] == 99.0
    assert first_year["high"] > first_year["open"]
    assert first_year["close"] > first_year["open"]
    assert first_year["volume"] > 1_000


def test_yearly_caps_at_fifteen_years(client, db, no_fetch):
    seed_series(db, "LONG", climbing_frame(20))
    bars = client.get("/stocks/LONG/price?resolution=yearly").json()["bars"]
    assert 10 <= len(bars) <= 16  # 15y window, boundary year may partially land


def test_yearly_short_history_returns_all_available(client, db, no_fetch):
    seed_series(db, "NEWCO", climbing_frame(2, start="2025-01-02"))
    r = client.get("/stocks/NEWCO/price?resolution=yearly")
    assert r.status_code == 200
    assert 1 <= len(r.json()["bars"]) <= 3


def test_monthly_window_is_three_years(client, db, no_fetch):
    seed_series(db, "MO", climbing_frame(10))
    bars = client.get("/stocks/MO/price?resolution=monthly").json()["bars"]
    # ~12 bars/year over a 3y window, with the boundary month partially landing
    assert 34 <= len(bars) <= 38


def test_weekly_window_is_five_years(client, db, no_fetch):
    seed_series(db, "WK", climbing_frame(10))
    bars = client.get("/stocks/WK/price?resolution=weekly").json()["bars"]
    assert 250 <= len(bars) <= 265


def test_all_resolutions_derive_from_the_same_stored_series(client, db, no_fetch):
    """FR-015/FR-016 — one series, four views of it. The daily close on the last
    bar must agree across resolutions."""
    seed_series(db, "SAME", climbing_frame(4))

    closes = {}
    for resolution in ("daily", "weekly", "monthly", "yearly"):
        bars = client.get(f"/stocks/SAME/price?resolution={resolution}").json()["bars"]
        closes[resolution] = bars[-1]["close"]

    assert len(set(closes.values())) == 1
