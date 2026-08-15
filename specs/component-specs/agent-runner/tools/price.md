# agent-runner/tools/price.py

> **Sourcing updated 2026-08-15** (specs/017-fmp-migration-admin): this module is now FMP-sourced, not yfinance. `get_price_history()` makes **one** FMP EOD fetch per ticker (`historical-price-eod/full`) and derives daily/weekly/monthly/quarterly/yearly by local pandas resample — previously three separate yfinance calls. `is_ticker_valid()` now checks FMP's `quote` endpoint instead of `fast_info`/`history`. The pseudocode below is retained for the resample/indicator logic, which is unchanged; treat any yfinance call shown as illustrative of the *replaced* behavior, not current code. See `specs/017-fmp-migration-admin/contracts/fmp-migration-map.md` (rows 1, 2, 7) and the real implementation in `agent-runner/tools/price.py` / `agent-runner/tools/fmp_client.py` for ground truth.

## Purpose
All price-related data fetching and technical indicator computation. Three exported functions, all used by TechnicalAnalyst.

## Functions

### `get_price_history(ticker: str, period: str = "1y") -> dict`
Fetches OHLCV history via yfinance, at five resolutions — skills need all
five for TFC (see `the-strat-spec.md` → "Time Frame Continuity (TFC)" and its
"Implementation Note" on this app's quarterly/yearly extension). yfinance has
no `"1y"` interval and its `"3mo"` interval would be a second, mostly
redundant network call, so quarterly and yearly are resampled from the
monthly fetch instead of pulled separately.

```python
import yfinance as yf

def get_price_history(ticker: str, period: str = "1y") -> dict:
    tk = yf.Ticker(ticker)
    daily = tk.history(period=period, interval="1d")
    weekly = tk.history(period="2y", interval="1wk")
    monthly = tk.history(period="5y", interval="1mo")

    def resample(df, rule):
        agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        return df.resample(rule).agg(agg).dropna(subset=["Open"])

    return {
        "daily": daily.reset_index().to_dict(orient="records"),
        "weekly": weekly.reset_index().to_dict(orient="records"),
        "monthly": monthly.reset_index().to_dict(orient="records"),
        "quarterly": resample(monthly, "QE").reset_index().to_dict(orient="records"),
        "yearly": resample(monthly, "YE").reset_index().to_dict(orient="records"),
        "ticker": ticker
    }
```

### `get_technical_indicators(ticker: str) -> dict`
Computes indicators on top of price history **directly with pandas** (updated
2026-08-02: pandas-ta 0.3.14b0 no longer exists on PyPI, and the 0.4.x betas are
a py3.12-only rewrite with a different API — the six indicators below are
standard formulas, implemented in `compute_indicators(df)` as a pure function so
they unit-test without network access. Column names: `RSI_14`, `MACD`,
`MACD_SIGNAL`, `MACD_HIST`, `BB_MID/UPPER/LOWER`, `ATR_14`, `VOLUME_SMA_20`,
`EMA_8/21/50/200`).

**Indicators computed:**
- RSI (14)
- MACD (12, 26, 9) — line, signal, histogram
- Bollinger Bands (20, 2)
- ATR (14) — for volatility-based stop sizing
- Volume SMA (20) — for relative volume spikes
- EMA (8, 21, 50, 200)

```python
import pandas_ta as ta

def get_technical_indicators(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    df = tk.history(period="1y", interval="1d")
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    df.ta.bbands(append=True)
    df.ta.atr(length=14, append=True)
    # ... etc
    return df.tail(30).to_dict(orient="records")  # last 30 days of signals
```

### `get_accumulation_score(ticker: str, lookback_days: int = 60) -> dict`
Thin wrapper that fetches price+volume data and calls `skills/accumulation.py`.

```python
from skills.accumulation import AccumulationSkill

def get_accumulation_score(ticker: str, lookback_days: int = 60) -> dict:
    tk = yf.Ticker(ticker)
    df = tk.history(period=f"{lookback_days}d", interval="1d")
    skill = AccumulationSkill()
    return skill.run(ticker, df)
```

### `is_ticker_valid(ticker: str) -> bool`
Cheap existence check run before a full crew analysis starts (see `crew.md` prefetch phase). Distinguishes "this ticker no longer trades" from a transient API hiccup, so the system can mark it `removed_from_market` in `ticker_index` instead of just logging a generic failure.

```python
def is_ticker_valid(ticker: str) -> bool:
    tk = yf.Ticker(ticker)
    try:
        fast = tk.fast_info
        has_price = fast.get("lastPrice") is not None
    except Exception:
        has_price = False

    if has_price:
        return True

    # fast_info can be flaky for thinly-traded names — fall back to a short history pull
    # before concluding the ticker is actually gone
    hist = tk.history(period="5d", interval="1d")
    return not hist.empty
```

Treated as a strong (not absolute) signal — yfinance occasionally has gaps for reasons other than delisting (API hiccups, brand-new IPOs). `crew.py` only raises `TickerDelistedError` when this check fails **and** the financials fetch also comes back empty, to avoid false positives from a single flaky source.

## Dependencies
- `yfinance`
- `pandas`
- `pandas-ta`
- `skills/accumulation.py`
