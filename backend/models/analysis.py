"""Spec: specs/component-specs/backend/models/analysis.md — flesh out in Phase 4."""
from datetime import datetime

from pydantic import BaseModel


class AnalysisSummary(BaseModel):
    ticker: str
    sector: str | None = None
    signal: str  # "bullish" | "bearish" | "neutral"
    conviction: str  # "high" | "medium" | "low"
    summary: str
    created_at: datetime
