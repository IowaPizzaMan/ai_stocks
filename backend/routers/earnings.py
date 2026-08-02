"""Spec: specs/component-specs/backend/routers/earnings.md"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/earnings", tags=["earnings"])


@router.get("/calendar")
def get_calendar(days: int = 7):
    raise HTTPException(501, "Not implemented — Phase 6")


@router.post("/scan")
def start_scan():
    raise HTTPException(501, "Not implemented — Phase 6")


@router.get("/scan/{scan_id}")
def get_scan(scan_id: str):
    raise HTTPException(501, "Not implemented — Phase 6")


@router.post("/analyze")
def analyze_selected():
    raise HTTPException(501, "Not implemented — Phase 6")


@router.get("/history/{ticker}")
def get_history(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 6")
