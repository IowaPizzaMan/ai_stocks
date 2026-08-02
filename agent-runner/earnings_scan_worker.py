"""Claims pending earnings scans from `earnings_scans` and runs the scanner.

The API container can't run the scanner itself (no agent-runner code, no
Ollama), so POST /earnings/scan just inserts a {status: "pending"} doc and
this worker — polled from main.py's loop alongside the work queue — picks it
up, runs agents/earnings_scanner.run_scan, and writes the results back onto
the same doc for the frontend to poll via GET /earnings/scan/{scan_id}.
"""
import logging
from datetime import datetime, timezone

from pymongo import ReturnDocument

from agents import earnings_scanner
from tools.db import EARNINGS_SCANS, get_db

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def claim_and_run_next_scan(db=None, run_scan=None) -> bool:
    """Claim the oldest pending scan and run it to completion.
    Returns False when there is nothing to do (caller sleeps)."""
    db = db if db is not None else get_db()
    run_scan = run_scan if run_scan is not None else earnings_scanner.run_scan

    scan = db[EARNINGS_SCANS].find_one_and_update(
        {"status": "pending"},
        {"$set": {"status": "running", "started_at": _utcnow()}},
        sort=[("requested_at", 1)],
        return_document=ReturnDocument.AFTER,
    )
    if scan is None:
        return False

    scan_id = scan["scan_id"]
    days_ahead = scan.get("days_ahead", 7)
    logger.info("claimed earnings scan %s (days_ahead=%s)", scan_id, days_ahead)

    try:
        result = run_scan(days_ahead=days_ahead, db=db)
        db[EARNINGS_SCANS].update_one(
            {"_id": scan["_id"]},
            {"$set": {"status": "complete", "completed_at": _utcnow(), **result}},
        )
        logger.info("earnings scan %s complete: %s scored of %s screened",
                    scan_id, result["scored_count"], result["total_screened"])
    except Exception as exc:
        logger.exception("earnings scan %s failed", scan_id)
        db[EARNINGS_SCANS].update_one(
            {"_id": scan["_id"]},
            {"$set": {"status": "failed", "error": str(exc), "completed_at": _utcnow()}},
        )
    return True
