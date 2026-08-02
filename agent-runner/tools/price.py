"""Price data + technical indicators. Spec: specs/component-specs/agent-runner/tools/price.md

Indicators are computed directly with pandas (pandas-ta 0.3.x was pulled from
PyPI and 0.4.x is an incompatible py3.12-only rewrite — see spec).
"""
import pandas as pd
import yfinance as yf


def _history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    return yf.Ticker(ticker).history(period=period, interval=interval)


def get_price_history(ticker: str, period: str = "1y") -> dict:
    """OHLCV history at daily/weekly/monthly resolution — skills need all three for TFC."""
    return {
        "daily": _history(ticker, period, "1d").reset_index().to_dict(orient="records"),
        "weekly": _history(ticker, "2y", "1wk").reset_index().to_dict(orient="records"),
        "monthly": _history(ticker, "5y", "1mo").reset_index().to_dict(orient="records"),
        "ticker": ticker,
    }


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Adds indicator columns to an OHLCV frame (index: date; columns include
    Open/High/Low/Close/Volume). Pure function so it's testable without yfinance."""
    out = df.copy()
    close, high, low = out["Close"], out["High"], out["Low"]

    # RSI 14 (Wilder smoothing)
    delta = close.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["RSI_14"] = 100 - 100 / (1 + avg_gain / avg_loss)

    # MACD 12/26/9
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_SIGNAL"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_HIST"] = out["MACD"] - out["MACD_SIGNAL"]

    # Bollinger Bands 20/2
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    out["BB_MID"] = mid
    out["BB_UPPER"] = mid + 2 * std
    out["BB_LOWER"] = mid - 2 * std

    # ATR 14 (Wilder) — for volatility-based stop sizing
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    out["ATR_14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    # Relative volume baseline
    out["VOLUME_SMA_20"] = out["Volume"].rolling(20).mean()

    # Trend EMAs
    for span in (8, 21, 50, 200):
        out[f"EMA_{span}"] = close.ewm(span=span, adjust=False).mean()

    return out


def get_technical_indicators(ticker: str) -> list[dict]:
    """Last 30 days of indicator signals on 1y of daily bars."""
    df = _history(ticker, "1y", "1d")
    return compute_indicators(df).tail(30).reset_index().to_dict(orient="records")


def get_accumulation_score(ticker: str, lookback_days: int = 60) -> dict:
    from skills import accumulation

    df = _history(ticker, f"{lookback_days}d", "1d")
    return accumulation.run(ticker, df)


def is_ticker_valid(ticker: str) -> bool:
    """Cheap existence check before a full crew run. Strong-but-not-absolute signal:
    crew.py only treats a ticker as delisted when financials also come back empty."""
    tk = yf.Ticker(ticker)
    try:
        has_price = tk.fast_info.get("lastPrice") is not None
    except Exception:
        has_price = False

    if has_price:
        return True

    # fast_info can be flaky for thinly-traded names — fall back to a short history
    # pull before concluding the ticker is actually gone
    try:
        hist = tk.history(period="5d", interval="1d")
    except Exception:
        return False
    return not hist.empty
