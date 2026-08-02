"""Spec: specs/component-specs/backend/routers/earnings.md

Not conversational — the scan produces a ranked table and selecting tickers
posts straight to the work queue. The scoring scan itself runs in the
agent-runner (it needs Ollama), so POST /scan just inserts a pending doc in
`earnings_scans` that earnings_scan_worker.py claims; the frontend polls
GET /scan/{scan_id} until it flips to complete/failed.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import earnings_data
from db import EARNINGS_SCANS, WORK_QUEUE
from deps import db_dependency
from registry import register_ticker

router = APIRouter(prefix="/earnings", tags=["earnings"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScanRequest(BaseModel):
    days_ahead: int = Field(default=7, ge=1, le=14)


class AnalyzeRequest(BaseModel):
    tickers: list[str]


@router.get("/calendar")
def get_calendar(days: int = 7, db=Depends(db_dependency)):
    """Pre-screened upcoming earnings (raw, unscored). Cached 4h.

    Read-only, deviating from the spec's auto-ingest design: during earnings
    season the calendar holds 600-900 names, and registering + enqueueing them
    all meant ~1-min crew runs for hours and a bloated ticker_index for Run
    All sweeps. Tickers enter the system one at a time instead — the user
    queues them from the calendar table via POST /earnings/analyze."""
    return earnings_data.get_earnings_calendar(days_ahead=days, db=db)


@router.post("/scan")
def start_scan(body: ScanRequest | None = None, db=Depends(db_dependency)):
    """Kick off a scoring scan (async, ~1-3 min). Poll GET /scan/{scan_id}."""
    body = body or ScanRequest()
    scan_id = str(uuid.uuid4())
    db[EARNINGS_SCANS].insert_one({
        "scan_id": scan_id,
        "status": "pending",
        "days_ahead": body.days_ahead,
        "requested_at": _utcnow(),
    })
    return {"scan_id": scan_id, "status": "pending"}


@router.get("/scan/{scan_id}")
def get_scan(scan_id: str, db=Depends(db_dependency)):
    doc = db[EARNINGS_SCANS].find_one({"scan_id": scan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Scan not found")
    return doc


@router.post("/analyze")
def analyze_selected(body: AnalyzeRequest, db=Depends(db_dependency)):
    """User picked tickers off the ranked list — enqueue full crew runs now."""
    enqueued = []
    for ticker in body.tickers:
        ticker = ticker.upper()
        register_ticker(db, ticker, source="earnings_scanner")
        existing = db[WORK_QUEUE].find_one(
            {"ticker": ticker, "status": {"$in": ["pending", "running"]}})
        if existing:
            continue
        db[WORK_QUEUE].insert_one({
            "ticker": ticker,
            "status": "pending",
            "source": "earnings_scanner",
            "parallel_prefetch": True,  # crew.py fans out its data fetch for these
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        })
        enqueued.append(ticker)
    return {"enqueued": enqueued}


@router.get("/history/{ticker}")
def get_history(ticker: str, db=Depends(db_dependency)):
    """Post-earnings move log — how the stock actually reacted to past prints."""
    return earnings_data.get_earnings_history(ticker.upper(), db=db)
