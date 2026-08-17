"""OHLCV price history for the frontend charts.

Not in the original component specs — added in Phase 5 because PriceChart.md
needs a dedicated price endpoint ("fetched from ... a dedicated price
endpoint") and none existed. Serves FMP bars (stable API) at the resolution
the chart requests, cached in Mongo for an hour so chart flipping doesn't
hammer FMP. Migrated off yfinance per specs/017-fmp-migration-admin.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from fastapi import APIRouter, Depends, HTTPException

from deps import db_dependency
from settings import settings

router = APIRouter(tags=["price"])

PRICE_CACHE = "price_cache"
CACHE_MINUTES = 60
FMP_BASE = "https://financialmodelingprep.com/stable/"

# resolution -> (period, interval) fetched
# each fetches enough history so the client's 200-period MAs are real
# monthly/yearly windows are sized to the Charts-tab panels (021): one candle
# per calendar month over ~3y, one per calendar year over ~15y
RESOLUTIONS = {
    "daily": ("2y", "1d"),
    "weekly": ("5y", "1wk"),
    "monthly": ("3y", "1mo"),
    "yearly": ("15y", "1y"),
}


@router.get("/stocks/{ticker}/price")
def get_price(ticker: str, resolution: str = "daily", db=Depends(db_dependency)):
    if resolution not in RESOLUTIONS:
        raise HTTPException(status_code=422,
                            detail=f"resolution must be one of {sorted(RESOLUTIONS)}")
    ticker = ticker.upper()

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=CACHE_MINUTES)
    cached = db[PRICE_CACHE].find_one(
        {"ticker": ticker, "resolution": resolution, "fetched_at": {"$gt": cutoff}},
        {"_id": 0},
    )
    if cached:
        return {"ticker": ticker, "resolution": resolution, "bars": cached["bars"]}

    period, interval = RESOLUTIONS[resolution]
    df = _fetch_history(ticker, period, interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}.")

    bars = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
        }
        for idx, row in df.iterrows()
        if row["Open"] == row["Open"] and row["High"] == row["High"]
        and row["Low"] == row["Low"] and row["Close"] == row["Close"]
    ]

    db[PRICE_CACHE].replace_one(
        {"ticker": ticker, "resolution": resolution},
        {"ticker": ticker, "resolution": resolution, "bars": bars,
         "fetched_at": datetime.now(timezone.utc)},
        upsert=True,
    )
    return {"ticker": ticker, "resolution": resolution, "bars": bars}


def _fetch_eod(ticker: str, years: int | None = None) -> pd.DataFrame:
    """Daily EOD bars. Without an explicit `from`, FMP returns only ~5 years —
    not enough for the yearly panel's 10–15 candles — so callers needing deep
    history pass the number of years they want (021: yearly resolution)."""
    url = f"{FMP_BASE}historical-price-eod/full?symbol={ticker}&apikey={settings.fmp_api_key}"
    if years:
        start = (datetime.now(timezone.utc) - timedelta(days=365 * years + 30)).strftime("%Y-%m-%d")
        url += f"&from={start}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    raw = r.json()
    rows = raw.get("historical", raw) if isinstance(raw, dict) else raw
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                              "close": "Close", "volume": "Volume"}
                     )[["Open", "High", "Low", "Close", "Volume"]]


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["Open"])


def _slice_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df.empty or period in ("max", None):
        return df
    if period.endswith("y"):
        cutoff = df.index.max() - pd.DateOffset(years=int(period[:-1]))
        return df[df.index >= cutoff]
    return df


def _fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Isolated for test monkeypatching."""
    years = int(period[:-1]) if period.endswith("y") else None
    # Only ask for deep history when the panel needs it — the default window
    # already covers daily/weekly/monthly and costs less to fetch and cache.
    daily = _fetch_eod(ticker, years=years if years and years > 5 else None)
    if interval == "1d":
        return _slice_period(daily, period)
    if interval == "1wk":
        return _slice_period(_resample(daily, "W"), period)
    if interval == "1mo":
        return _slice_period(_resample(daily, "ME"), period)
    if interval == "1y":
        return _slice_period(_resample(daily, "YE"), period)
    raise ValueError(f"unsupported interval: {interval}")
