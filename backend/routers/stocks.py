"""Spec: specs/component-specs/backend/routers/stocks.md"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/search")
def search(q: str):
    raise HTTPException(501, "Not implemented — Phase 4")


@router.get("/{ticker}")
def get_ticker(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 4")


@router.get("/{ticker}/financials")
def get_financials(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 4")


@router.get("/{ticker}/signals")
def get_signals(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 4")
