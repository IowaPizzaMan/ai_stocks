"""Spec: specs/component-specs/backend/routers/watchlist.md"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("")
def get_watchlist():
    raise HTTPException(501, "Not implemented — Phase 4")


@router.post("/{ticker}")
def add_to_watchlist(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 4")


@router.delete("/{ticker}")
def remove_from_watchlist(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 4")
