"""Spec: specs/component-specs/backend/routers/earnings.md

Not conversational — selecting tickers off the calendar posts straight to the
work queue. `POST /scan` and `GET /scan/{scan_id}` remain below for the
agent-runner's scoring worker, but specs/025-earnings-page-filters removed
their only caller (the frontend's manual scan trigger); they are dormant, not
deleted (KNOWN_ISSUES.md).
"""
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import earnings_data
from db import EARNINGS_SCANS, WORK_QUEUE
from deps import db_dependency
from fmp import FmpBudgetExceededError
from registry import register_ticker

router = APIRouter(prefix="/earnings", tags=["earnings"])

MAX_CALENDAR_SPAN_DAYS = 90


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScanRequest(BaseModel):
    days_ahead: int = Field(default=7, ge=1, le=14)


class AnalyzeRequest(BaseModel):
    tickers: list[str]


@router.get("/calendar")
def get_calendar(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db=Depends(db_dependency),
):
    """Every company >=$500M cap reporting between `from` and `to` (inclusive),
    with actuals/surprise for anything already reported. Cached 4h per exact
    window (contracts/earnings-calendar.md, specs/025-earnings-page-filters).

    Read-only, deviating from the original spec's auto-ingest design: during
    earnings season the calendar holds hundreds of names, and registering +
    enqueueing them all meant ~1-min crew runs for hours and a bloated
    ticker_index for Run All sweeps. Tickers enter the system one at a time
    instead — the user queues them from the calendar table via
    POST /earnings/analyze."""
    if from_ > to:
        raise HTTPException(status_code=422, detail="'from' must not be after 'to'")
    if (to - from_).days > MAX_CALENDAR_SPAN_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"date range too wide (max {MAX_CALENDAR_SPAN_DAYS} days)",
        )

    try:
        return earnings_data.get_earnings_calendar(start=from_, end=to, db=db)
    except FmpBudgetExceededError:
        raise HTTPException(
            status_code=503,
            detail="Earnings calendar temporarily unavailable — FMP daily budget spent",
        ) from None
    except earnings_data.CalendarUnavailableError:
        raise HTTPException(
            status_code=502, detail="Earnings calendar provider unavailable") from None
    except earnings_data.UniverseUnavailableError:
        raise HTTPException(status_code=502, detail="Company universe unavailable") from None


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
