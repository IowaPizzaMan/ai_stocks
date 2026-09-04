"""Stock activity feed + per-stock change history.
Spec: specs/037-stocks-conviction-and-activity; contracts/stock-events-api.md.

Read-only — stock_events is written by agent-runner (register_ticker,
queue_worker.py) and by registry.py's own mirrored "added" writer; nothing
here writes.
"""
from fastapi import APIRouter, Depends, Query

from db import STOCK_EVENTS
from deps import db_dependency

router = APIRouter(prefix="/events", tags=["events"])

# The activity feed's hard cap (FR-019) — a property of this endpoint, not of
# the collection: `total` is capped here, not derived from a collection-wide
# count.
WINDOW = 100

_PROJECTION = {"_id": 0, "source": 0}


@router.get("")
def get_activity_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(db_dependency),
):
    skip = (page - 1) * page_size
    limit = max(0, min(page_size, WINDOW - skip))
    items = [] if limit == 0 else list(
        db[STOCK_EVENTS].find({}, _PROJECTION)
        .sort("occurred_at", -1)
        .skip(skip)
        .limit(limit)
    )
    total = min(db[STOCK_EVENTS].count_documents({}), WINDOW)
    return {"items": items, "total": total, "page": page, "page_size": page_size, "window": WINDOW}


@router.get("/{ticker}")
def get_ticker_change_history(
    ticker: str,
    limit: int = Query(20, ge=1, le=50),
    db=Depends(db_dependency),
):
    # FR-029 — an "updated" event that changed nothing appears in the global
    # feed above but not here; this is what makes that feed a superset of a
    # ticker's change history rather than a separate, potentially-diverging
    # writer (research R6).
    filter = {
        "ticker": ticker.upper(),
        "$or": [{"event_type": "added"}, {"changed": True}],
    }
    items = list(
        db[STOCK_EVENTS].find(filter, _PROJECTION)
        .sort("occurred_at", -1)
        .limit(limit)
    )
    return {"ticker": ticker.upper(), "items": items, "total": len(items), "limit": limit}
