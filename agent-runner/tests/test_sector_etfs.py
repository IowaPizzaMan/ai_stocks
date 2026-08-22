"""sector_etf_pull — the 11-ticker sector ETF price refresh.
Spec: specs/028-dashboard-tweaks-batch US5.
Contract: specs/028-dashboard-tweaks-batch/contracts/sector-etf-series-api.md

price_store.get_series is used unchanged (R5) — these tests exercise the
looping/fail-soft wrapper only, monkeypatching get_series itself rather than
price_store's own provider seam (that's price_store's own test's job).
"""
import mongomock
import pandas as pd
import pytest

from tools import sector_etfs


@pytest.fixture
def db():
    return mongomock.MongoClient()["sector_etfs_test"]


def bars_frame(n=5):
    return pd.DataFrame({"Close": [100.0 + i for i in range(n)]})


def test_attempts_all_eleven_tickers(db, monkeypatch):
    attempted = []

    def fake_get_series(ticker, refresh="none", db=None):
        attempted.append(ticker)
        return bars_frame(), {"requests": 1, "retrieval": "incremental", "outcome": "fetched"}

    monkeypatch.setattr(sector_etfs.price_store, "get_series", fake_get_series)

    sector_etfs.run_sector_etf_pull(db)

    assert sorted(attempted) == sorted(sector_etfs.SECTOR_ETFS)
    assert len(attempted) == 11


def test_one_ticker_raising_does_not_abort_the_others(db, monkeypatch):
    def flaky_get_series(ticker, refresh="none", db=None):
        if ticker == "XLK":
            raise RuntimeError("provider exploded")
        return bars_frame(), {"requests": 1, "retrieval": "incremental", "outcome": "fetched"}

    monkeypatch.setattr(sector_etfs.price_store, "get_series", flaky_get_series)

    count = sector_etfs.run_sector_etf_pull(db)

    assert count == 10  # every ticker except the one that raised


def test_returns_count_of_tickers_with_usable_bars(db, monkeypatch):
    def fake_get_series(ticker, refresh="none", db=None):
        if ticker == "XLRE":
            return pd.DataFrame(), {"requests": 1, "retrieval": "full", "outcome": "degraded"}
        return bars_frame(), {"requests": 1, "retrieval": "incremental", "outcome": "fetched"}

    monkeypatch.setattr(sector_etfs.price_store, "get_series", fake_get_series)

    count = sector_etfs.run_sector_etf_pull(db)

    assert count == 10  # XLRE returned no bars, so it doesn't count as usable


def test_uses_delta_refresh(db, monkeypatch):
    refreshes = []

    def fake_get_series(ticker, refresh="none", db=None):
        refreshes.append(refresh)
        return bars_frame(), {"requests": 1, "retrieval": "incremental", "outcome": "fetched"}

    monkeypatch.setattr(sector_etfs.price_store, "get_series", fake_get_series)

    sector_etfs.run_sector_etf_pull(db)

    assert all(r == "delta" for r in refreshes)


def test_sector_etfs_list_is_the_eleven_spdr_sector_tickers():
    assert set(sector_etfs.SECTOR_ETFS) == {
        "XLC", "XLY", "XLP", "XLE", "XLF", "XLI", "XLV", "XLB", "XLRE", "XLK", "XLU",
    }
