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
    BENEFICIAL_OWNERSHIP_CACHE,
    EARNINGS_CACHE,
    FINANCIALS_CACHE,
    INSTITUTIONAL_CACHE,
    INSTITUTIONAL_FLOW,
    PULL_METRICS,
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


MAX_PULL_METRICS = 20


@router.get("/stocks/{ticker}/pull-metrics")
def get_pull_metrics(ticker: str, limit: int = 1, db=Depends(db_dependency)):
    """Recent pull-cost breakdowns for a ticker (024 US1).

    Stages come back most-expensive-first and unaccounted time is computed here
    rather than in the client: SC-006 asks the operator to spot the top three
    stages without extra work, and FR-004 wants the time the breakdown cannot
    explain to be visible rather than silently dropped.
    """
    ticker = ticker.upper()
    limit = max(1, min(limit, MAX_PULL_METRICS))

    docs = list(
        db[PULL_METRICS]
        .find({"ticker": ticker}, {"_id": 0})
        .sort("started_at", -1)
        .limit(limit)
    )
    if not docs:
        raise HTTPException(status_code=404, detail="No pull recorded for this ticker.")

    pulls = []
    for doc in docs:
        stages = sorted(doc.get("stages", []),
                        key=lambda s: s.get("elapsed_ms", 0), reverse=True)
        accounted = sum(s.get("elapsed_ms", 0) for s in stages)
        total = doc.get("total_ms", 0)
        pulls.append({
            **doc,
            "stages": stages,
            "accounted_ms": accounted,
            # Clamped: a stage clock overrunning the pull clock is a bug, but it
            # should not surface to the operator as negative time.
            "unaccounted_ms": max(0, total - accounted),
        })
    return {"ticker": ticker, "pulls": pulls}
