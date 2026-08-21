"""Spec: specs/component-specs/backend/routers/queue.md

The frontend's "Pull" / "Run All" buttons land here; the agent-runner polls
work_queue directly — no direct connection between this API and that process.

024-delta-data-pulls adds a per-job `mode`. Delta is the default and the only
thing "Run All" ever queues; `mode=full` is the operator's per-ticker escape
hatch for rebuilding stored data from scratch.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from db import TICKER_INDEX, WORK_QUEUE
from deps import db_dependency
from registry import register_ticker

router = APIRouter(prefix="/queue", tags=["queue"])

DELTA = "delta"
FULL = "full"
MODES = (DELTA, FULL)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enqueue(db, ticker: str, source: str = "manual", mode: str = DELTA) -> dict:
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
        existing_mode = existing.get("mode") or DELTA
        # A full refresh arriving while a delta job is still *pending* upgrades
        # that job in place. Reporting "already queued" here would tell the
        # operator their request was handled and then hand them a delta pull
        # (024 research D8). A job already running is too late to upgrade — say
        # so plainly rather than implying a full refresh is underway.
        if mode == FULL and existing_mode != FULL and existing["status"] == "pending":
            db[WORK_QUEUE].update_one(
                {"_id": existing["_id"]},
                {"$set": {"mode": FULL, "updated_at": _utcnow()}},
            )
            return {"ticker": ticker, "job_id": str(existing["_id"]),
                    "status": "upgraded_to_full", "mode": FULL}
        return {"ticker": ticker, "job_id": str(existing["_id"]),
                "status": "already_queued", "mode": existing_mode}

    result = db[WORK_QUEUE].insert_one({
        "ticker": ticker, "status": "pending", "source": source, "mode": mode,
        "created_at": _utcnow(), "updated_at": _utcnow(),
    })
    return {"ticker": ticker, "job_id": str(result.inserted_id),
            "status": "enqueued", "mode": mode}


@router.get("")
def get_queue(db=Depends(db_dependency)):
    def shape(job: dict) -> dict:
        # Absent mode = queued before 024 shipped; it will run as a delta.
        return {**job, "mode": job.get("mode") or DELTA}

    pending = [shape(j) for j in db[WORK_QUEUE].find({"status": "pending"}, {"_id": 0}).sort("created_at", 1)]
    running = [shape(j) for j in db[WORK_QUEUE].find({"status": "running"}, {"_id": 0})]
    return {"pending": pending, "running": running,
            "pending_count": len(pending), "running_count": len(running)}


@router.post("/all")
def enqueue_all(db=Depends(db_dependency)):
    """Run All — sweep every active ticker in the registry (not just the
    watchlist). Deliberately delta-only: a bulk full refresh would be the most
    expensive thing in the app and is out of scope (024 spec, Out of Scope)."""
    universe = list(db[TICKER_INDEX].find({"status": "active"}, {"ticker": 1, "_id": 0}))
    enqueued, already = [], []
    for item in universe:
        result = _enqueue(db, item["ticker"])
        (enqueued if result["status"] == "enqueued" else already).append(item["ticker"])
    return {"enqueued": enqueued, "already_queued": already, "universe_size": len(universe)}


@router.post("/{ticker}")
def enqueue_ticker(ticker: str, mode: str = DELTA, db=Depends(db_dependency)):
    if mode not in MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {list(MODES)}")
    return _enqueue(db, ticker, mode=mode)
