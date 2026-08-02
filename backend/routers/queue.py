"""Spec: specs/component-specs/backend/routers/queue.md"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("")
def get_queue():
    raise HTTPException(501, "Not implemented — Phase 4")


@router.post("/all")
def enqueue_all():
    """Run All — enqueue every active ticker in ticker_index."""
    raise HTTPException(501, "Not implemented — Phase 4")


@router.post("/{ticker}")
def enqueue_ticker(ticker: str):
    raise HTTPException(501, "Not implemented — Phase 4")
