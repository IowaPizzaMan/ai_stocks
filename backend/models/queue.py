"""Spec: specs/component-specs/backend/models/queue.md — flesh out in Phase 4."""
from datetime import datetime

from pydantic import BaseModel


class QueueJob(BaseModel):
    ticker: str
    status: str  # "pending" | "running" | "done" | "failed"
    source: str
    created_at: datetime
    updated_at: datetime | None = None
