"""Spec: specs/component-specs/backend/routers/sectors.md"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/sectors", tags=["sectors"])


@router.get("")
def get_sectors():
    raise HTTPException(501, "Not implemented — Phase 4")
