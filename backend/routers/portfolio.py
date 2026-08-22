"""Cross-stock AI summary panel on the Stocks page — specs/027.

Read-only over a singleton `portfolio_digest_cache` document written by the
agent-runner's `portfolio_digest` admin job (see
agent-runner/tools/portfolio.py); this router never calls an LLM or a
provider itself. `POST /regenerate` only ever enqueues that job into the
existing `work_queue`, deduped like a per-ticker Pull.
Contract: specs/027-stocks-news-tab-ai-summary/contracts/portfolio-digest-api.md
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from db import PORTFOLIO_DIGEST_CACHE, WORK_QUEUE
from deps import db_dependency

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.get("/digest")
def get_digest(db=Depends(db_dependency)):
    """Always 200 — this backs a panel on the app's home page (mirrors
    `/market/news`'s reasoning): no document yet is a valid empty state, not
    an error."""
    doc = db[PORTFOLIO_DIGEST_CACHE].find_one({}, {"_id": 0})
    if not doc:
        return {
            "as_of": None,
            "overview": None,
            "highlights": [],
            "stock_count": 0,
            "total_tracked_count": 0,
            "capped": False,
            "stale": False,
        }

    generated_at = doc.get("generated_at")
    last_error_at = doc.get("last_error_at")
    # A failure before any success ever landed has nothing to mark stale —
    # that's still the plain empty state (FR-011), not an error state.
    stale = bool(
        generated_at is not None
        and last_error_at is not None
        and _as_utc(last_error_at) > _as_utc(generated_at)
    )

    return {
        "as_of": _as_utc(generated_at).isoformat() if generated_at else None,
        "overview": doc.get("overview"),
        "highlights": doc.get("highlights", []),
        "stock_count": doc.get("stock_count", 0),
        "total_tracked_count": doc.get("total_tracked_count", 0),
        "capped": doc.get("capped", False),
        "stale": stale,
    }


@router.post("/digest/regenerate")
def regenerate_digest(db=Depends(db_dependency)):
    existing = db[WORK_QUEUE].find_one(
        {"job_type": "portfolio_digest", "status": {"$in": ["pending", "running"]}}
    )
    if existing:
        return {"status": "already_queued", "job_id": str(existing["_id"])}

    result = db[WORK_QUEUE].insert_one({
        "job_type": "portfolio_digest",
        "status": "pending",
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    })
    return {"status": "enqueued", "job_id": str(result.inserted_id)}
