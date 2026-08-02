"""Spec: specs/component-specs/backend/routers/watchlist.md

The user's pinned subset of tickers. Adding here also registers the ticker in
the system-wide registry so Run All sweeps pick it up.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import ANALYSES, WATCHLIST
from deps import db_dependency
from registry import register_ticker

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class AddToWatchlistRequest(BaseModel):
    name: str | None = None
    sector: str | None = None


@router.get("")
def get_watchlist(db=Depends(db_dependency)):
    items = list(db[WATCHLIST].find({}, {"_id": 0}))
    for item in items:
        latest = db[ANALYSES].find_one(
            {"ticker": item["ticker"]},
            {"signal": 1, "conviction": 1, "timestamp": 1, "_id": 0},
            sort=[("timestamp", -1)],
        )
        if latest:
            item["last_signal"] = latest.get("signal")
            item["last_conviction"] = latest.get("conviction")
            item["last_analyzed"] = latest.get("timestamp")
        item.setdefault("status", "active")
    return {"items": items, "count": len(items)}


@router.post("/{ticker}")
def add_to_watchlist(ticker: str, body: AddToWatchlistRequest | None = None,
                     db=Depends(db_dependency)):
    ticker = ticker.upper()
    body = body or AddToWatchlistRequest()
    if db[WATCHLIST].find_one({"ticker": ticker}):
        raise HTTPException(status_code=409, detail=f"{ticker} already in watchlist.")

    register_ticker(db, ticker, source="watchlist", name=body.name, sector=body.sector)

    item = {"ticker": ticker, "name": body.name, "sector": body.sector,
            "status": "active", "added_at": datetime.now(timezone.utc)}
    db[WATCHLIST].insert_one(item)
    item.pop("_id", None)
    return item


@router.delete("/{ticker}")
def remove_from_watchlist(ticker: str, db=Depends(db_dependency)):
    result = db[WATCHLIST].delete_one({"ticker": ticker.upper()})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist.")
    return {"removed": ticker.upper()}
