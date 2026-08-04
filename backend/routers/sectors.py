"""Spec: specs/component-specs/backend/routers/sectors.md

Sector-level rollups of the latest analysis per ticker. The heavy lift
(latest-per-ticker) runs in Mongo; the per-sector rollup happens in Python —
it's one row per ticker at that point, and this keeps the counting logic
plain enough to read.
"""
from fastapi import APIRouter, Depends

from db import ANALYSES
from deps import db_dependency
from routers.analysis import get_sector_analyses

router = APIRouter(prefix="/sectors", tags=["sectors"])

_SIGNAL_RANK = {"bullish": 2, "neutral": 1, "bearish": 0}
_CONVICTION_RANK = {"high": 2, "medium": 1, "low": 0}


@router.get("")
def get_sectors(db=Depends(db_dependency)):
    pipeline = [
        {"$match": {"sector": {"$nin": [None, ""]}}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$ticker", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0, "ticker": 1, "sector": 1, "signal": 1, "conviction": 1}},
    ]
    latest = list(db[ANALYSES].aggregate(pipeline))

    sectors: dict[str, dict] = {}
    for doc in latest:
        s = sectors.setdefault(doc["sector"], {
            "sector": doc["sector"],
            "bullish_count": 0, "bearish_count": 0, "neutral_count": 0,
            "ticker_count": 0, "_best": None,
        })
        if f"{doc.get('signal')}_count" in s:
            s[f"{doc['signal']}_count"] += 1
        s["ticker_count"] += 1
        # top ticker = most bullish, conviction breaking ties
        key = (_SIGNAL_RANK.get(doc["signal"], 0), _CONVICTION_RANK.get(doc["conviction"], 0))
        if s["_best"] is None or key > s["_best"][0]:
            s["_best"] = (key, doc["ticker"])

    out = []
    for s in sorted(sectors.values(), key=lambda x: x["sector"]):
        best = s.pop("_best")
        s["top_ticker"] = best[1] if best else None
        out.append(s)
    return out


@router.get("/{sector}")
def get_sector_detail(sector: str, db=Depends(db_dependency)):
    """Alias of GET /analysis/sector/{sector} for semantic URL clarity."""
    return get_sector_analyses(sector, db=db)
