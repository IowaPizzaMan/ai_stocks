"""Spec: specs/component-specs/backend/routers/macro.md"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("")
def get_macro():
    raise HTTPException(501, "Not implemented — Phase 4")
