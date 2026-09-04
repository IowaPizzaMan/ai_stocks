"""Shared ticker registry upsert. Spec: specs/component-specs/backend/db.md

Mirror of agent-runner/tools/db.py::register_ticker — keep the two in sync by
hand (the agent-runner writes to Mongo directly, not through this API).
"""
from datetime import datetime, timezone

from pymongo.database import Database

from db import STOCK_EVENTS, TICKER_INDEX


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
    result = db[TICKER_INDEX].update_one({"ticker": ticker}, update, upsert=True)
    # 037-stocks-conviction-and-activity — mirrors agent-runner/tools/db.py's
    # register_ticker: `upserted_id` is only set on an actual insert, so this
    # is race-free and idempotent on repeat registration (constitution
    # Principle VI — the two services share no Python package, so this small
    # bit of write logic is duplicated by hand rather than imported).
    if result.upserted_id is not None:
        db[STOCK_EVENTS].insert_one({
            "ticker": ticker, "event_type": "added", "occurred_at": now,
            "changed": False, "changes": None, "reason": None, "source": "backend_api",
        })
