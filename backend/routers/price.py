"""OHLCV price history for the frontend charts.

Not in the original component specs — added in Phase 5 because PriceChart.md
needs a dedicated price endpoint ("fetched from ... a dedicated price
endpoint") and none existed. Serves yfinance bars at the resolution the chart
requests, cached in Mongo for an hour so chart flipping doesn't hammer Yahoo.
"""
from datetime import datetime, timedelta, timezone

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException

from deps import db_dependency

router = APIRouter(tags=["price"])

PRICE_CACHE = "price_cache"
CACHE_MINUTES = 60

# resolution -> (yfinance interval, period fetched)
# each fetches ≥200 bars of history so the client's 200-period MAs are real
RESOLUTIONS = {
    "daily": ("1d", "2y"),
    "weekly": ("1wk", "5y"),
    "monthly": ("1mo", "max"),
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

    interval, period = RESOLUTIONS[resolution]
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


def _fetch_history(ticker: str, period: str, interval: str):
    """Isolated for test monkeypatching."""
    return yf.Ticker(ticker).history(period=period, interval=interval)
