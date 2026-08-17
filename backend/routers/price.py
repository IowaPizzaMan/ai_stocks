"""OHLCV price history for the frontend charts.

Not in the original component specs — added in Phase 5 because PriceChart.md
needs a dedicated price endpoint ("fetched from ... a dedicated price
endpoint") and none existed. Migrated off yfinance per
specs/017-fmp-migration-admin.

Reworked by specs/024-delta-data-pulls: this used to keep FOUR cache documents
per ticker — one per chart resolution — each triggering its own full history
download when its 60-minute TTL lapsed, so flipping between chart tabs cost four
full downloads of the same underlying data. Now there is one maintained daily
series per ticker (price_store) and every resolution is resampled from it
locally, so switching resolutions costs zero requests (FR-015, FR-016, SC-004).

The provider call also now routes through fmp.fmp_get rather than a bare
requests.get, so it counts against the daily budget (Principle IV) — half of a
logged KNOWN_ISSUES.md entry.
"""
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import price_store
from deps import db_dependency

router = APIRouter(tags=["price"])

# resolution -> (resample rule, display window)
# Resample rule None means the stored daily series is already the right grain.
# Windows are sized to the Charts-tab panels (021): one candle per calendar
# month over ~3y, one per calendar year over ~15y.
RESOLUTIONS = {
    "daily": (None, "2y"),
    "weekly": ("W", "5y"),
    "monthly": ("ME", "3y"),
    "yearly": ("YE", "15y"),
}


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


@router.get("/stocks/{ticker}/price")
def get_price(ticker: str, resolution: str = "daily", db=Depends(db_dependency)):
    if resolution not in RESOLUTIONS:
        raise HTTPException(status_code=422,
                            detail=f"resolution must be one of {sorted(RESOLUTIONS)}")
    ticker = ticker.upper()

    # Refresh only when there is nothing stored — a page view should not be able
    # to trigger a download for a ticker the pull pipeline already maintains
    # (FR-016). Everything else resamples from what we hold.
    stored, _ = price_store.get_series(ticker, refresh="none", db=db)
    if stored.empty:
        stored, _ = price_store.get_series(ticker, refresh="delta", db=db)

    if stored.empty:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}.")

    rule, window = RESOLUTIONS[resolution]
    df = _slice_period(_resample(stored, rule) if rule else stored, window)

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
    return {"ticker": ticker, "resolution": resolution, "bars": bars}
