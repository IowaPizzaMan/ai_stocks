"""Spec: specs/component-specs/backend/routers/stocks.md

Stock search, per-ticker data endpoints, and registry admin (list / disable /
delete / bulk add). No router prefix — this module serves both /stocks/* and
/tickers* paths.
"""
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import ReturnDocument

from db import (
    ANALYSES,
    BENEFICIAL_OWNERSHIP_CACHE,
    COMPANY_INFO,
    EARNINGS_CACHE,
    FINANCIALS_CACHE,
    INSTITUTIONAL_CACHE,
    INSTITUTIONAL_FLOW,
    STOCK_NEWS_CACHE,
    TICKER_INDEX,
    TRANSCRIPTS_CACHE,
    WATCHLIST,
    WORK_QUEUE,
)
from deps import db_dependency
from registry import register_ticker

router = APIRouter(tags=["stocks"])

TICKER_PATTERN = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")


class TickerStatusUpdate(BaseModel):
    status: str  # "active" | "disabled"


class BulkAddRequest(BaseModel):
    tickers: str


class SentimentUpdate(BaseModel):
    sentiment: Literal["liked", "disliked"]


@router.get("/stocks/search")
def search_stocks(q: str, limit: int = 10, db=Depends(db_dependency)):
    regex = {"$regex": f"^{re.escape(q)}", "$options": "i"}
    results = list(db[TICKER_INDEX].find(
        {"$or": [{"ticker": regex}, {"name": regex}]}, {"_id": 0}
    ).limit(limit))

    for r in results:
        r.setdefault("status", "active")
        latest = db[ANALYSES].find_one(
            {"ticker": r["ticker"]},
            {"signal": 1, "conviction": 1, "timestamp": 1, "_id": 0},
            sort=[("timestamp", -1)],
        )
        if latest:
            r.update(latest)
    return results


@router.get("/tickers")
def list_tickers(status: str | None = None, db=Depends(db_dependency)):
    filter = {"status": status} if status else {}
    items = list(db[TICKER_INDEX].find(filter, {"_id": 0}).sort("ticker", 1))
    return {
        "items": items,
        "total": len(items),
        "active_count": sum(1 for i in items if i.get("status", "active") == "active"),
        "disabled_count": sum(1 for i in items if i.get("status") == "disabled"),
        "removed_count": sum(1 for i in items if i.get("status") == "removed_from_market"),
    }


@router.patch("/tickers/{ticker}")
def update_ticker_status(ticker: str, body: TickerStatusUpdate, db=Depends(db_dependency)):
    updated = db[TICKER_INDEX].find_one_and_update(
        {"ticker": ticker.upper()},
        {"$set": {"status": body.status}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Unknown ticker.")
    return updated


@router.delete("/tickers/{ticker}")
def delete_ticker(ticker: str, db=Depends(db_dependency)):
    """Destructive: removes the registry entry AND all cached data for the ticker."""
    ticker = ticker.upper()
    result = db[TICKER_INDEX].delete_one({"ticker": ticker})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Unknown ticker.")

    db[ANALYSES].delete_many({"ticker": ticker})
    db[FINANCIALS_CACHE].delete_many({"ticker": ticker})
    db[WATCHLIST].delete_one({"ticker": ticker})
    db[WORK_QUEUE].delete_many({"ticker": ticker, "status": {"$in": ["pending", "running"]}})
    db[INSTITUTIONAL_FLOW].delete_many({"ticker": ticker})
    db[TRANSCRIPTS_CACHE].delete_many({"ticker": ticker})
    db[STOCK_NEWS_CACHE].delete_many({"ticker": ticker})
    db[INSTITUTIONAL_CACHE].delete_many({"ticker": ticker})
    db[BENEFICIAL_OWNERSHIP_CACHE].delete_many({"ticker": ticker})
    # earnings_cache also holds market-wide "calendar"/"universe" docs with no
    # ticker field — only the per-ticker "history" docs belong to this ticker.
    db[EARNINGS_CACHE].delete_many({"type": "history", "ticker": ticker})
    return {"deleted": ticker}


@router.post("/tickers/bulk")
def bulk_add_tickers(body: BulkAddRequest, db=Depends(db_dependency)):
    candidates = [t for t in re.split(r"[\s,]+", body.tickers.strip().upper()) if t]

    added, already_existed, invalid = [], [], []
    seen = set()
    for ticker in candidates:
        if ticker in seen:
            continue
        seen.add(ticker)

        if not TICKER_PATTERN.match(ticker):
            invalid.append(ticker)
            continue

        existing = db[TICKER_INDEX].find_one({"ticker": ticker})
        if existing:
            already_existed.append(ticker)
            if existing.get("status") != "active":
                # pasting a ticker in is an explicit "track this again"
                db[TICKER_INDEX].update_one({"ticker": ticker}, {"$set": {"status": "active"}})
        else:
            added.append(ticker)

        register_ticker(db, ticker, source="manual")

    return {"added": added, "already_existed": already_existed, "invalid": invalid}


@router.get("/stocks/industries")
def list_industries(db=Depends(db_dependency)):
    """Distinct industries among tracked (non-removed) tickers, sorted —
    sourced from ticker_index so the industry filter can never offer a choice
    that yields an empty grid (contracts/sector-and-industry.md, FR-024).
    Registered before /stocks/{ticker} — Starlette matches path routes in
    registration order, so a literal segment must precede a wildcard one or
    "industries" would be swallowed as a ticker symbol."""
    values = db[TICKER_INDEX].distinct(
        "industry", {"industry": {"$nin": [None, ""]}, "status": {"$ne": "removed_from_market"}}
    )
    return {"industries": sorted(values)}


@router.get("/stocks/{ticker}")
def get_ticker(ticker: str, db=Depends(db_dependency)):
    record = db[TICKER_INDEX].find_one({"ticker": ticker.upper()}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Unknown ticker.")
    return record


@router.put("/stocks/{ticker}/sentiment")
def set_sentiment(ticker: str, body: SentimentUpdate, db=Depends(db_dependency)):
    """Like/dislike (specs/028-dashboard-tweaks-batch US3). 404s when the
    ticker isn't tracked (FR-006a) — a tag can only ever exist for a stock the
    feed filter can actually surface (R11). Re-sending the currently-stored
    value toggles it off (FR-008); the two states are mutually exclusive by
    construction since it's a single field (FR-007)."""
    ticker = ticker.upper()
    existing = db[TICKER_INDEX].find_one({"ticker": ticker}, {"sentiment": 1})
    if not existing:
        raise HTTPException(status_code=404, detail=f"{ticker} is not tracked.")

    if existing.get("sentiment") == body.sentiment:
        db[TICKER_INDEX].update_one(
            {"ticker": ticker},
            {"$set": {"sentiment": None, "sentiment_at": None}},
        )
        return {"ticker": ticker, "sentiment": None}

    db[TICKER_INDEX].update_one(
        {"ticker": ticker},
        {"$set": {"sentiment": body.sentiment, "sentiment_at": datetime.now(timezone.utc)}},
    )
    return {"ticker": ticker, "sentiment": body.sentiment}


@router.delete("/stocks/{ticker}/sentiment")
def clear_sentiment(ticker: str, db=Depends(db_dependency)):
    ticker = ticker.upper()
    result = db[TICKER_INDEX].update_one(
        {"ticker": ticker},
        {"$set": {"sentiment": None, "sentiment_at": None}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"{ticker} is not tracked.")
    return {"ticker": ticker, "sentiment": None}


@router.get("/stocks/{ticker}/financials")
def get_financials(ticker: str, db=Depends(db_dependency)):
    cached = db[FINANCIALS_CACHE].find_one({"ticker": ticker.upper()}, {"_id": 0})
    if not cached:
        raise HTTPException(status_code=404,
                            detail="No financial data cached for this ticker. Run analysis first.")
    return cached["data"]


@router.get("/stocks/{ticker}/signals")
def get_signals(ticker: str, db=Depends(db_dependency)):
    doc = db[ANALYSES].find_one({"ticker": ticker.upper()}, {"_id": 0}, sort=[("timestamp", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No analysis found for this ticker.")
    return {"ticker": doc["ticker"], "timestamp": doc["timestamp"], **doc.get("sub_reports", {})}


def _split_range(range_str: str | None) -> tuple[float | None, float | None]:
    """FMP's 52-week range comes as "224.69-344.57" (contracts/company-profile-api.md)."""
    if not range_str or "-" not in range_str:
        return None, None
    low, _, high = range_str.partition("-")
    try:
        return float(low), float(high)
    except ValueError:
        return None, None


@router.get("/stocks/{ticker}/profile")
def get_company_profile(ticker: str, db=Depends(db_dependency)):
    """Cache-only read (Principle IV — never issues a provider call). 404
    means "never fetched", distinct from a 200 with sparse fields for an
    ETF/fund. price/change/change_percentage/volume are deliberately
    excluded (FR-011b) — the frontend derives those from price bars instead,
    so this section can never disagree with the Charts tab (research R7)."""
    doc = db[COMPANY_INFO].find_one({"ticker": ticker.upper()}, {"_id": 0})
    if not doc or not doc.get("profile"):
        raise HTTPException(status_code=404, detail="No profile cached for this ticker.")
    p = doc["profile"]
    range_low, range_high = _split_range(p.get("range"))
    return {
        "ticker": ticker.upper(),
        "name": p.get("name"),
        "exchange": p.get("exchange"),
        "exchange_full": p.get("exchange_full"),
        "sector": p.get("sector"),
        "industry": p.get("industry"),
        "country": p.get("country"),
        "currency": p.get("currency"),
        "website": p.get("website"),
        "ceo": p.get("ceo"),
        "full_time_employees": p.get("full_time_employees"),
        "ipo_date": p.get("ipo_date"),
        "description": p.get("description"),
        "logo_url": None if p.get("default_image") or not p.get("image") else p.get("image"),
        "market_cap": p.get("market_cap"),
        "beta": p.get("beta"),
        "last_dividend": p.get("last_dividend"),
        "range_low": range_low,
        "range_high": range_high,
        "average_volume": p.get("average_volume"),
        "is_etf": p.get("is_etf", False),
        "is_fund": p.get("is_fund", False),
        "is_actively_trading": p.get("is_actively_trading"),
        "fetched_at": doc.get("profile_fetched_at"),
    }


@router.get("/stocks/{ticker}/peers")
def get_company_peers(ticker: str, db=Depends(db_dependency)):
    """Always 200 — empty is a valid state, not an error. Sorted server-side
    (market cap descending, nulls last, symbol tiebreak) so every client gets
    the same order (contracts/company-profile-api.md, research R8)."""
    doc = db[COMPANY_INFO].find_one({"ticker": ticker.upper()}, {"_id": 0})
    peers = (doc or {}).get("peers") or []
    ordered = sorted(
        peers,
        key=lambda p: (p.get("market_cap") is None, -(p.get("market_cap") or 0), p.get("symbol") or ""),
    )
    return {"ticker": ticker.upper(), "peers": ordered, "fetched_at": (doc or {}).get("peers_fetched_at")}


@router.get("/stocks/{ticker}/employee-count")
def get_employee_count(ticker: str, db=Depends(db_dependency)):
    """Always 200. Sorted ascending by period so the chart plots
    chronologically without client-side sorting (FR-015)."""
    doc = db[COMPANY_INFO].find_one({"ticker": ticker.upper()}, {"_id": 0})
    records = sorted((doc or {}).get("employee_counts") or [], key=lambda r: r.get("period_of_report") or "")
    return {
        "ticker": ticker.upper(),
        "records": records,
        "fetched_at": (doc or {}).get("employee_counts_fetched_at"),
    }
