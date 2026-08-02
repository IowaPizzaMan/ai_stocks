"""Spec: specs/component-specs/backend/routers/analysis.md"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/feed")
def get_feed(page: int = 1):
    raise HTTPException(501, "Not implemented — Phase 4")


@router.get("/{ticker}")
def get_ticker_analysis(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 4")


@router.get("/sector/{sector}")
def get_sector_analyses(sector: str):
    raise HTTPException(501, "Not implemented — Phase 4")
