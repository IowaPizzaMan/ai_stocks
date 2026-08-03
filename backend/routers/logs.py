"""Relays client-side error reports into logs/frontend/. Spec: specs/SPEC.md
'Exception Handling & Logging'.

Browsers can't write local files directly, so the frontend's ErrorBoundary
and window.onerror/onunhandledrejection hooks (errorLogger.ts) POST here
instead, and this router writes them via the shared get_logger() helper --
same choke point, same eventual cloud-sink swap, as every other component.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from logging_config import get_logger

router = APIRouter(prefix="/logs", tags=["logs"])

# component="frontend" so these land in logs/frontend/frontend.log instead
# of logs/backend/backend.log.
logger = get_logger(__name__, component="frontend")


class FrontendErrorReport(BaseModel):
    message: str
    stack: str | None = None
    component: str | None = None
    url: str | None = None
    timestamp: str | None = None


@router.post("/frontend")
def report_frontend_error(report: FrontendErrorReport) -> dict:
    logger.error(
        "frontend error: %s | component=%s url=%s client_timestamp=%s\n%s",
        report.message, report.component, report.url, report.timestamp,
        report.stack or "(no stack)",
    )
    return {"status": "logged"}
