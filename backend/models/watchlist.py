"""Spec: specs/component-specs/backend/models/watchlist.md — flesh out in Phase 4."""
from pydantic import BaseModel


class WatchlistEntry(BaseModel):
    ticker: str
