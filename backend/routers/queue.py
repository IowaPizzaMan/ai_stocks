"""Spec: specs/component-specs/backend/routers/queue.md

The frontend's "Pull" / "Run All" buttons land here; the agent-runner polls
work_queue directly — no direct connection between this API and that process.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from db import TICKER_INDEX, WORK_QUEUE
from deps import db_dependency
from registry import register_ticker

router = APIRouter(prefix="/queue", tags=["queue"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enqueue(db, ticker: str, source: str = "manual") -> dict:
    ticker = ticker.upper()

    record = db[TICKER_INDEX].find_one({"ticker": ticker})
    if record and record.get("status") == "removed_from_market":
        # The user explicitly asked for this ticker — reactivate rather than
        # silently skip (maybe it relisted, or delisting was a false positive)
        db[TICKER_INDEX].update_one(
            {"ticker": ticker},
            {"$set": {"status": "active"}, "$unset": {"delisted_at": "", "delisted_reason": ""}},
        )

    register_ticker(db, ticker, source=source)

    existing = db[WORK_QUEUE].find_one({"ticker": ticker, "status": {"$in": ["pending", "running"]}})
    if existing:
        return {"ticker": ticker, "job_id": str(existing["_id"]), "status": "already_queued"}

    result = db[WORK_QUEUE].insert_one({
        "ticker": ticker, "status": "pending", "source": source,
        "created_at": _utcnow(), "updated_at": _utcnow(),
    })
    return {"ticker": ticker, "job_id": str(result.inserted_id), "status": "enqueued"}


@router.get("")
def get_queue(db=Depends(db_dependency)):
    pending = list(db[WORK_QUEUE].find({"status": "pending"}, {"_id": 0}).sort("created_at", 1))
    running = list(db[WORK_QUEUE].find({"status": "running"}, {"_id": 0}))
    return {"pending": pending, "running": running,
            "pending_count": len(pending), "running_count": len(running)}


@router.post("/all")
def enqueue_all(db=Depends(db_dependency)):
    """Run All — sweep every active ticker in the registry (not just the watchlist)."""
    universe = list(db[TICKER_INDEX].find({"status": "active"}, {"ticker": 1, "_id": 0}))
    enqueued, already = [], []
    for item in universe:
        result = _enqueue(db, item["ticker"])
        (enqueued if result["status"] == "enqueued" else already).append(item["ticker"])
    return {"enqueued": enqueued, "already_queued": already, "universe_size": len(universe)}


@router.post("/{ticker}")
def enqueue_ticker(ticker: str, db=Depends(db_dependency)):
    return _enqueue(db, ticker)
