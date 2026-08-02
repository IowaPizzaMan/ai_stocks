"""Spec: specs/component-specs/backend/routers/institutional_flow.md"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/institutional", tags=["institutional-flow"])


@router.get("/flow")
def get_flow(page: int = 1):
    raise HTTPException(501, "Not implemented — Phase 7")


@router.get("/flow/{ticker}")
def get_ticker_flow(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 7")


@router.post("/scan")
def trigger_scan():
    raise HTTPException(501, "Not implemented — Phase 7")
