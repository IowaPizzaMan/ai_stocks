"""Spec: specs/component-specs/backend/routers/analysis.md"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends

from db import ANALYSES
from deps import db_dependency

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/feed")
def get_feed(
    page: int = 1,
    page_size: int = 20,
    ticker: str | None = None,
    signal: str | None = None,
    sector: str | None = None,
    conviction: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    db=Depends(db_dependency),
):
    filter: dict = {}
    if ticker:
        # substring match so partial typing narrows as-you-go (FilterBar search)
        filter["ticker"] = {"$regex": re.escape(ticker), "$options": "i"}
    if signal:
        filter["signal"] = signal
    if sector:
        filter["sector"] = sector
    if conviction:
        filter["conviction"] = conviction
    if from_date or to_date:
        filter["timestamp"] = {}
        if from_date:
            filter["timestamp"]["$gte"] = from_date
        if to_date:
            filter["timestamp"]["$lte"] = to_date

    # sub_reports are far too large for the feed — project them out
    projection = {"_id": 0, "sub_reports": 0}
    total = db[ANALYSES].count_documents(filter)
    items = list(
        db[ANALYSES].find(filter, projection)
        .sort("timestamp", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sector/{sector}")
def get_sector_analyses(sector: str, db=Depends(db_dependency)):
    """Most recent analysis per ticker within a sector."""
    pipeline = [
        {"$match": {"sector": sector}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$ticker", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0, "sub_reports": 0}},
    ]
    return list(db[ANALYSES].aggregate(pipeline))


@router.get("/{ticker}")
def get_ticker_analysis(ticker: str, db=Depends(db_dependency)):
    return db[ANALYSES].find_one({"ticker": ticker.upper()}, {"_id": 0})
