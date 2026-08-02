"""Shared ticker registry upsert. Spec: specs/component-specs/backend/db.md

Mirror of agent-runner/tools/db.py::register_ticker — keep the two in sync by
hand (the agent-runner writes to Mongo directly, not through this API).
"""
from datetime import datetime, timezone

from pymongo.database import Database

from db import TICKER_INDEX


def register_ticker(db: Database, ticker: str, source: str,
                    name: str | None = None, sector: str | None = None) -> None:
    """Upsert into ticker_index. Called by queue/watchlist/earnings routers.

    source: "manual" | "watchlist" | "earnings_calendar" | "institutional_flow"
    """
    ticker = ticker.upper()
    now = datetime.now(timezone.utc)
    update = {
        "$addToSet": {"sources": source},
        "$set": {"last_seen_at": now},
        "$setOnInsert": {"ticker": ticker, "first_seen_at": now, "status": "active"},
    }
    if name:
        update["$set"]["name"] = name
    if sector:
        update["$set"]["sector"] = sector
    db[TICKER_INDEX].update_one({"ticker": ticker}, update, upsert=True)
