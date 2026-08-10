"""Claims jobs from work_queue, dispatches the crew, marks done/failed.
Spec: specs/component-specs/agent-runner/queue_worker.md

On TickerDelistedError the ticker is flagged `removed_from_market` in
ticker_index (and the watchlist entry, if any) so Run All sweeps skip it and
the UI can badge it — distinct from ordinary transient failures, which stay
active and get retried on the next run.
"""
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from crew import Crew, TickerDelistedError
from logging_config import get_logger
from tools.db import ANALYSES, WORK_QUEUE, ensure_indexes, get_db, mark_ticker_removed, sanitize_floats

logger = get_logger(__name__)

STALE_RUNNING_MINUTES = 30

_started = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def recover_stale_jobs(db) -> int:
    """Reset jobs stuck in 'running' from a prior crash back to 'pending'."""
    cutoff = _utcnow() - timedelta(minutes=STALE_RUNNING_MINUTES)
    result = db[WORK_QUEUE].update_many(
        {"status": "running", "started_at": {"$lt": cutoff}},
        {"$set": {"status": "pending", "updated_at": _utcnow()}},
    )
    if result.modified_count:
        logger.warning("reset %s stale running job(s) to pending", result.modified_count)
    return result.modified_count


def _startup(db) -> None:
    global _started
    if not _started:
        ensure_indexes(db)
        recover_stale_jobs(db)
        _started = True


def claim_and_run_next(db=None, crew=None) -> bool:
    """Claim the oldest pending job and run it to completion.
    Returns False when the queue is empty (caller sleeps), True otherwise."""
    db = db if db is not None else get_db()
    _startup(db)

    job = db[WORK_QUEUE].find_one_and_update(
        {"status": "pending"},
        {"$set": {"status": "running", "started_at": _utcnow(), "updated_at": _utcnow()}},
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )
    if job is None:
        return False

    ticker = job["ticker"]
    logger.info("claimed job %s for %s", job["_id"], ticker)
    crew = crew if crew is not None else Crew(db=db)

    try:
        # earnings-scanner jobs opt in to parallel prefetch (user picked them
        # from a ranked list and is waiting on the result)
        result = crew.run(ticker, parallel_prefetch=bool(job.get("parallel_prefetch")))
        result = sanitize_floats(result)
        db[ANALYSES].insert_one(result)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "done", "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )
        logger.info("%s analysis done (signal=%s conviction=%s)",
                    ticker, result.get("signal"), result.get("conviction"))
    except TickerDelistedError as exc:
        logger.warning("%s appears delisted — marking removed_from_market", exc.ticker)
        mark_ticker_removed(exc.ticker, reason=str(exc), db=db)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "failed", "delisted": True, "error": str(exc),
                      "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )
    except Exception as exc:
        logger.exception("%s job failed", ticker)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "failed", "delisted": False, "error": str(exc),
                      "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )

    return True
