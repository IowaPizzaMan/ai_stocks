"""Unit tests for tools/price.py — FMP is faked; no network."""
import numpy as np
import pandas as pd
import pytest
import requests

from tools import price


def make_ohlcv(rows: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, rows))
    high = close + rng.uniform(0.1, 2, rows)
    low = close - rng.uniform(0.1, 2, rows)
    df = pd.DataFrame(
        {
            "Open": close + rng.normal(0, 0.5, rows),
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, rows),
        },
        index=pd.date_range("2025-01-01", periods=rows, freq="B", name="Date"),
    )
    return df


@pytest.fixture
def fake_eod(monkeypatch):
    """Monkeypatches fetch_eod_history to return a fixed frame, recording
    every (ticker) call — mirrors the old fake_ticker fixture's role."""
    calls: list = []

    def factory(df=None):
        frame = df if df is not None else make_ohlcv()

        def _fetch(ticker, db=None):
            calls.append(ticker)
            return frame

        monkeypatch.setattr(price, "fetch_eod_history", _fetch)
        return calls

    return factory


def test_get_price_history_shape(fake_eod):
    calls = fake_eod()
    result = price.get_price_history("AAPL")

    assert result["ticker"] == "AAPL"
    assert set(result) == {"daily", "weekly", "monthly", "quarterly", "yearly", "ticker"}
    # single fetch backs all five resolutions (previously three separate calls)
    assert calls == ["AAPL"]
    first = result["daily"][0]
    assert {"Open", "High", "Low", "Close", "Volume", "Date"} <= set(first)

    quarterly, yearly = result["quarterly"], result["yearly"]
    assert quarterly and yearly
    assert {"Open", "High", "Low", "Close", "Volume", "Date"} <= set(quarterly[0])
    assert len(yearly) <= len(quarterly) <= len(result["monthly"])


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
    np.testing.assert_allclose(
        tail["MACD_HIST"], tail["MACD"] - tail["MACD_SIGNAL"], rtol=1e-9
    )


def test_get_technical_indicators_returns_last_30(fake_eod):
    fake_eod()
    records = price.get_technical_indicators("MSFT")
    assert len(records) == 30
    assert "RSI_14" in records[0]


def test_is_ticker_valid_true_when_quote_has_price(monkeypatch):
    monkeypatch.setattr(price, "fmp_get", lambda path: [{"symbol": "AAPL", "price": 231.5}])
    assert price.is_ticker_valid("AAPL") is True


def test_is_ticker_valid_false_when_empty_list(monkeypatch):
    monkeypatch.setattr(price, "fmp_get", lambda path: [])
    assert price.is_ticker_valid("GONE") is False


def test_is_ticker_valid_false_on_http_error(monkeypatch):
    def _raise(path):
        response = requests.Response()
        response.status_code = 404
        raise requests.HTTPError("404", response=response)

    monkeypatch.setattr(price, "fmp_get", _raise)
    assert price.is_ticker_valid("GONE") is False


def test_is_ticker_valid_true_under_budget_pressure(monkeypatch):
    """Can't verify under budget pressure — don't false-flag as delisted."""
    from tools.fmp_client import FmpBudgetExceededError

    def _raise(path):
        raise FmpBudgetExceededError("cap exceeded")

    monkeypatch.setattr(price, "fmp_get", _raise)
    assert price.is_ticker_valid("AAPL") is True
