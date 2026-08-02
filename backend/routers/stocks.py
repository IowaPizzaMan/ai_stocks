"""Spec: specs/component-specs/backend/routers/stocks.md

Stock search, per-ticker data endpoints, and registry admin (list / disable /
delete / bulk add). No router prefix — this module serves both /stocks/* and
/tickers* paths.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import ReturnDocument

from db import (
    ANALYSES,
    FINANCIALS_CACHE,
    INSTITUTIONAL_FLOW,
    TICKER_INDEX,
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


@router.get("/stocks/{ticker}")
def get_ticker(ticker: str, db=Depends(db_dependency)):
    record = db[TICKER_INDEX].find_one({"ticker": ticker.upper()}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Unknown ticker.")
    return record


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
