"""Spec: specs/component-specs/backend/models/institutional_flow.md — flesh out in Phase 7."""
from datetime import datetime

from pydantic import BaseModel


class InstitutionalFlowEvent(BaseModel):
    fund: str
    ticker: str
    action: str  # "new_position" | "add" | "trim" | "exit"
    notability: float
    filed_at: datetime
