"""Spec: specs/component-specs/backend/models/ticker.md — flesh out in Phase 4."""
from datetime import datetime

from pydantic import BaseModel


class TickerRecord(BaseModel):
    ticker: str
    status: str = "active"  # "active" | "removed_from_market"
    source: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
