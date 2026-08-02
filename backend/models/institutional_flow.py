"""Spec: specs/component-specs/backend/models/institutional_flow.md"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class InstitutionalFlowEvent(BaseModel):
    ticker: str
    fund: str
    action: Literal["new_position", "add", "trim", "exit"]
    shares: int | None = None
    value_usd: float | None = None
    pct_of_portfolio: float | None = None
    pct_change: float | None = None  # QoQ position change (13F rows), 1.0 = +100%
    headline: str
    notability_score: int  # 0-100, higher = more likely a high-conviction signal
    source: Literal["13F", "dataroma"]
    filed_at: datetime
    scanned_at: datetime


class InstitutionalFlowResponse(BaseModel):
    items: list[InstitutionalFlowEvent]
    total: int
    page: int
    page_size: int


class InstitutionalScanResult(BaseModel):
    status: Literal["queued"]
    message: str
