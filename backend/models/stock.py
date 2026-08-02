"""Spec: specs/component-specs/backend/models/stock.md — flesh out in Phase 4."""
from pydantic import BaseModel


class StockSearchResult(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
