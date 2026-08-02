"""Shared ticker registry upsert. Spec: specs/SPEC.md 'Ticker Registry & Delisting Detection'."""
from datetime import datetime, timezone

from db import TICKER_INDEX, get_db


def register_ticker(ticker: str, source: str) -> None:
    """Upsert into ticker_index. Called by queue/watchlist/earnings routers.

    source: "manual" | "watchlist" | "earnings_calendar" | "institutional_flow"
    """
    get_db()[TICKER_INDEX].update_one(
        {"ticker": ticker.upper()},
        {
            "$setOnInsert": {
                "ticker": ticker.upper(),
                "status": "active",
                "first_seen": datetime.now(timezone.utc),
                "source": source,
            },
            "$set": {"last_seen": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
