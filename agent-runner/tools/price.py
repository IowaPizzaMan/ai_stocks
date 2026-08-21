"""Price data + technical indicators. Spec: specs/component-specs/agent-runner/tools/price.md

Indicators are computed directly with pandas (pandas-ta 0.3.x was pulled from
PyPI and 0.4.x is an incompatible py3.12-only rewrite — see spec).

Sourced from FMP (stable API) as of specs/017-fmp-migration-admin — yfinance
is retired. get_price_history() derives weekly/monthly/quarterly/yearly by
local resample instead of separate network calls per resolution.

As of specs/024-delta-data-pulls these read the maintained daily series from
tools/price_store.py with refresh="none" — the series is refreshed exactly once
per pull by Crew._prefetch, so the three readers here can no longer each
trigger their own download (FR-014, SC-003; previously `price` and `indicators`
downloaded the same full history twice in one pull).
"""
import pandas as pd

from tools import price_store
from tools.fmp_client import FmpBudgetExceededError, fmp_get


def _slice_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Approximates yfinance's `period` window (e.g. '1y', '5d', 'max') on an
    already-fetched, ascending-date DataFrame."""
    if df.empty or period in ("max", None):
        return df
    if period.endswith("mo"):
        cutoff = df.index.max() - pd.DateOffset(months=int(period[:-2]))
    elif period.endswith("y"):
        cutoff = df.index.max() - pd.DateOffset(years=int(period[:-1]))
    elif period.endswith("d"):
        return df.tail(int(period[:-1]))
    else:
        return df
    return df[df.index >= cutoff]


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Aggregates an OHLCV frame up to a coarser bar resolution (weekly,
    monthly, and — from monthly — quarterly/yearly, none of which FMP's daily
    endpoint returns directly)."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["Open"])


def get_price_history(ticker: str, period: str = "1y", db=None) -> dict:
    """OHLCV history at daily/weekly/monthly/quarterly/yearly resolution —
    skills need all five for TFC. One stored series backs all five; weekly/
    monthly/quarterly/yearly are resampled locally."""
    daily_full, _ = price_store.get_series(ticker, refresh="none", db=db)
    monthly_full = _resample(daily_full, "ME")
    return {
        "daily": _slice_period(daily_full, period).reset_index().to_dict(orient="records"),
        "weekly": _slice_period(_resample(daily_full, "W"), "2y").reset_index().to_dict(orient="records"),
        "monthly": _slice_period(monthly_full, "5y").reset_index().to_dict(orient="records"),
        "quarterly": _resample(monthly_full, "QE").reset_index().to_dict(orient="records"),
        "yearly": _resample(monthly_full, "YE").reset_index().to_dict(orient="records"),
        "ticker": ticker,
    }


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Adds indicator columns to an OHLCV frame (index: date; columns include
    Open/High/Low/Close/Volume). Pure function so it's testable without a
    live data source."""
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


def get_technical_indicators(ticker: str, db=None) -> list[dict]:
    """Last 30 days of indicator signals on 1y of daily bars."""
    series, _ = price_store.get_series(ticker, refresh="none", db=db)
    df = _slice_period(series, "1y")
    return compute_indicators(df).tail(30).reset_index().to_dict(orient="records")


def get_accumulation_score(ticker: str, lookback_days: int = 60, db=None) -> dict:
    from skills import accumulation

    series, _ = price_store.get_series(ticker, refresh="none", db=db)
    df = _slice_period(series, f"{lookback_days}d")
    return accumulation.run(ticker, df)


def is_ticker_valid(ticker: str) -> bool:
    """Cheap existence check before a full crew run. Strong-but-not-absolute
    signal: crew.py only treats a ticker as delisted when financials also
    come back empty."""
    try:
        data = fmp_get(f"quote?symbol={ticker}")
    except FmpBudgetExceededError:
        return True  # can't verify under budget pressure — don't false-flag as delisted
    except Exception:
        return False
    return bool(data) and isinstance(data, list) and data[0].get("price") is not None
