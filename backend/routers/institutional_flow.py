"""Spec: specs/component-specs/backend/routers/institutional_flow.md

Market-wide flow feed. The scan itself runs in the agent-runner (Playwright +
Ollama live there), so POST /scan just raises the manual_scan_requested flag
in institutional_flow_meta; institutional_flow_worker.py claims it on its
next poll tick.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from db import INSTITUTIONAL_FLOW, INSTITUTIONAL_FLOW_META
from deps import db_dependency
from models.institutional_flow import (
    InstitutionalFlowEvent,
    InstitutionalFlowResponse,
    InstitutionalScanResult,
)

router = APIRouter(prefix="/institutional", tags=["institutional-flow"])


@router.get("/flow", response_model=InstitutionalFlowResponse)
def get_flow(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = None,
    fund: str | None = None,
    ticker: str | None = None,
    min_notability: int | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    db=Depends(db_dependency),
):
    filter: dict = {}
    if action:
        filter["action"] = action
    if fund:
        filter["fund"] = {"$regex": fund, "$options": "i"}
    if ticker:
        filter["ticker"] = ticker.upper()
    if min_notability is not None:
        filter["notability_score"] = {"$gte": min_notability}
    if from_date or to_date:
        filter["filed_at"] = {}
        if from_date:
            filter["filed_at"]["$gte"] = from_date
        if to_date:
            filter["filed_at"]["$lte"] = to_date

    total = db[INSTITUTIONAL_FLOW].count_documents(filter)
    items = list(
        db[INSTITUTIONAL_FLOW].find(filter, {"_id": 0})
        .sort("filed_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/flow/{ticker}", response_model=list[InstitutionalFlowEvent])
def get_ticker_flow(ticker: str, limit: int = Query(default=20, ge=1, le=100),
                    db=Depends(db_dependency)):
    return list(
        db[INSTITUTIONAL_FLOW].find({"ticker": ticker.upper()}, {"_id": 0})
        .sort("filed_at", -1)
        .limit(limit)
    )


@router.post("/scan", response_model=InstitutionalScanResult)
def trigger_scan(db=Depends(db_dependency)):
    db[INSTITUTIONAL_FLOW_META].update_one(
        {"key": "manual_scan_requested"},
        {"$set": {"value": True, "requested_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"status": "queued",
            "message": "Institutional flow scan requested — results will appear shortly."}
