"""Unit tests for tools/price.py — yfinance is faked; no network."""
import numpy as np
import pandas as pd
import pytest

from tools import price


def make_ohlcv(rows: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, rows))
    high = close + rng.uniform(0.1, 2, rows)
    low = close - rng.uniform(0.1, 2, rows)
    return pd.DataFrame(
        {
            "Open": close + rng.normal(0, 0.5, rows),
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, rows),
        },
        index=pd.date_range("2025-01-01", periods=rows, freq="B", name="Date"),
    )


class FakeTicker:
    def __init__(self, ticker, history_df=None, fast_info=None, raise_fast_info=False):
        self._df = history_df if history_df is not None else make_ohlcv()
        self._fast_info = fast_info or {}
        self._raise = raise_fast_info
        self.history_calls = []

    def history(self, period=None, interval=None):
        self.history_calls.append((period, interval))
        return self._df

    @property
    def fast_info(self):
        if self._raise:
            raise RuntimeError("fast_info unavailable")
        return self._fast_info


@pytest.fixture
def fake_ticker(monkeypatch):
    calls: list = []

    def factory(**kwargs):
        def _ctor(symbol):
            tk = FakeTicker(symbol, **kwargs)
            tk.history_calls = calls  # shared across instances — one Ticker per fetch
            return tk

        monkeypatch.setattr(price.yf, "Ticker", _ctor)
        return calls

    return factory


def test_get_price_history_shape(fake_ticker):
    calls = fake_ticker()
    result = price.get_price_history("AAPL")

    assert result["ticker"] == "AAPL"
    assert set(result) == {"daily", "weekly", "monthly", "ticker"}
    assert calls == [("1y", "1d"), ("2y", "1wk"), ("5y", "1mo")]
    first = result["daily"][0]
    assert {"Open", "High", "Low", "Close", "Volume", "Date"} <= set(first)


def test_compute_indicators_columns_and_ranges():
    df = price.compute_indicators(make_ohlcv())
    expected = {
        "RSI_14", "MACD", "MACD_SIGNAL", "MACD_HIST",
        "BB_MID", "BB_UPPER", "BB_LOWER", "ATR_14", "VOLUME_SMA_20",
        "EMA_8", "EMA_21", "EMA_50", "EMA_200",
    }
    assert expected <= set(df.columns)

    tail = df.tail(30)
    assert tail["RSI_14"].between(0, 100).all()
    assert (tail["BB_UPPER"] >= tail["BB_MID"]).all()
    assert (tail["BB_MID"] >= tail["BB_LOWER"]).all()
    assert (tail["ATR_14"] > 0).all()
    # MACD histogram is line minus signal by construction
    np.testing.assert_allclose(
        tail["MACD_HIST"], tail["MACD"] - tail["MACD_SIGNAL"], rtol=1e-9
    )


def test_get_technical_indicators_returns_last_30(fake_ticker):
    fake_ticker()
    records = price.get_technical_indicators("MSFT")
    assert len(records) == 30
    assert "RSI_14" in records[0]


def test_is_ticker_valid_via_fast_info(fake_ticker):
    fake_ticker(fast_info={"lastPrice": 123.45})
    assert price.is_ticker_valid("AAPL") is True


def test_is_ticker_valid_falls_back_to_history(fake_ticker):
    fake_ticker(fast_info={}, history_df=make_ohlcv(rows=5))
    assert price.is_ticker_valid("THIN") is True


def test_is_ticker_valid_false_when_all_empty(fake_ticker):
    fake_ticker(raise_fast_info=True, history_df=pd.DataFrame())
    assert price.is_ticker_valid("GONE") is False
