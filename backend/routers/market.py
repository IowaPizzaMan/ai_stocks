"""Spec: specs/component-specs/frontend/components/stock/BreadthDivergenceChart.md

Read-only view over what the agent-runner's daily breadth pass already wrote to
Mongo — no computation here. The oscillator math, SPY fetch and divergence
detection all live in agent-runner/tools/breadth.py; this router just serves
the cached series so the frontend can draw them.
"""
from fastapi import APIRouter, Depends, Query

from db import BREADTH_CACHE, BREADTH_DIVERGENCES, BREADTH_META, MARKET_FLOW_EVENTS
from deps import db_dependency

router = APIRouter(prefix="/market", tags=["market"])

NO_DIVERGENCE = {"type": "none", "description": "no breadth data yet",
                 "price_points": [], "osc_points": []}


def _rows(db, exchange: str, lookback_days: int) -> list[dict]:
    """Cached breadth rows for one exchange, oldest first."""
    rows = list(
        db[BREADTH_CACHE]
        .find({"exchange": exchange}, {"_id": 0, "date": 1, "mcclellan": 1, "spy_close": 1})
        .sort("date", -1)
        .limit(lookback_days)
    )
    return list(reversed(rows))


@router.get("/breadth")
def get_breadth(lookback_days: int = Query(default=60, ge=10, le=250),
                db=Depends(db_dependency)):
    nyse = _rows(db, "nyse", lookback_days)
    nasdaq = _rows(db, "nasdaq", lookback_days)
    meta = db[BREADTH_META].find_one({"key": "last_divergence"})
    history = list(
        db[BREADTH_DIVERGENCES]
        .find({"resolved": {"$ne": None}}, {"_id": 0})
        .sort("resolved", -1)
        .limit(20)
    )

    return {
        # SPY is stored on the nyse rows — the divergence read is SPY vs NYMO
        "spy": [{"date": r["date"], "close": r["spy_close"]}
                for r in nyse if r.get("spy_close") is not None],
        "nymo": [{"date": r["date"], "value": r["mcclellan"]} for r in nyse],
        "namo": [{"date": r["date"], "value": r["mcclellan"]} for r in nasdaq],
        "divergence": (meta or {}).get("value") or NO_DIVERGENCE,
        "divergence_history": list(reversed(history)),
        "as_of": nyse[-1]["date"] if nyse else None,
        "method": "computed_ratio_adjusted",
    }


@router.get("/flow-events")
def get_flow_events(limit: int = Query(default=5, ge=1, le=50),
                    db=Depends(db_dependency)):
    """Market-wide events (currently breadth divergences) for the feed —
    ticker-less, so they can't ride the per-ticker analysis feed."""
    return list(
        db[MARKET_FLOW_EVENTS].find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    )
