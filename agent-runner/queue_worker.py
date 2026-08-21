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
from tools.admin_jobs import JOB_DATASETS, JOB_HANDLERS, STALE_MINUTES
from tools.db import (
    ANALYSES,
    PULL_METRICS,
    WORK_QUEUE,
    ensure_indexes,
    get_db,
    mark_ticker_removed,
    sanitize_floats,
    write_db,
    write_dataset_meta,
)

logger = get_logger(__name__)

STALE_RUNNING_MINUTES = 30

_started = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def recover_stale_jobs(db) -> int:
    """Reset jobs stuck in 'running' from a prior crash back to 'pending'.
    Admin jobs may override the default 30-minute staleness allowance via
    tools.admin_jobs.STALE_MINUTES (e.g. a long-running scrape)."""
    now = _utcnow()
    modified = 0
    for job_type, minutes in STALE_MINUTES.items():
        cutoff = now - timedelta(minutes=minutes)
        result = db[WORK_QUEUE].update_many(
            {"status": "running", "job_type": job_type, "started_at": {"$lt": cutoff}},
            {"$set": {"status": "pending", "updated_at": now}},
        )
        modified += result.modified_count

    default_cutoff = now - timedelta(minutes=STALE_RUNNING_MINUTES)
    result = db[WORK_QUEUE].update_many(
        {
            "status": "running",
            "job_type": {"$nin": list(STALE_MINUTES.keys())},
            "started_at": {"$lt": default_cutoff},
        },
        {"$set": {"status": "pending", "updated_at": now}},
    )
    modified += result.modified_count

    if modified:
        logger.warning("reset %s stale running job(s) to pending", modified)
    return modified


def _startup(db) -> None:
    global _started
    if not _started:
        ensure_indexes(db)
        recover_stale_jobs(db)
        _started = True


def _run_admin_job(db, job) -> bool:
    """Dispatches a non-ticker work_queue job (job_type set, no ticker) to
    its registered handler. Returns True (job was claimed and processed)."""
    job_type = job["job_type"]
    handler = JOB_HANDLERS.get(job_type)
    dataset = JOB_DATASETS.get(job_type)

    if handler is None:
        logger.error("no handler registered for job_type=%s", job_type)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "failed", "error": "no handler for job_type",
                      "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )
        return True

    try:
        record_count = handler(db)
        if dataset:
            write_dataset_meta(dataset, "success", record_count=record_count or 0, db=db)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "done", "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )
        logger.info("admin job %s done (job_type=%s, record_count=%s)", job["_id"], job_type, record_count)
    except Exception as exc:
        logger.exception("admin job %s failed (job_type=%s)", job["_id"], job_type)
        if dataset:
            write_dataset_meta(dataset, "failed", db=db)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "failed", "error": str(exc),
                      "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )
    return True


def _write_pull_metrics(db, job, crew, outcome: str) -> None:
    """Persists the pull-cost breakdown for this job (024 US1, FR-001..FR-004).

    A crew that reports nothing (a stub, or a run that raised before finishing
    prefetch) simply writes nothing — measurement is diagnostic and must never
    become a precondition for running an analysis.
    """
    pull = getattr(crew, "last_pull", None)
    if not pull:
        return
    db[PULL_METRICS].insert_one({
        "ticker": job["ticker"],
        "job_id": str(job["_id"]),
        "mode": pull.get("mode", "delta"),
        "started_at": pull.get("started_at"),
        "completed_at": pull.get("completed_at"),
        "total_ms": pull.get("total_ms", 0),
        "outcome": outcome,
        "stages": pull.get("stages", []),
    })


def _record_pull_metrics(db, job, crew, outcome: str) -> None:
    """FR-005 — a failure in measurement must not cost us the analysis."""
    try:
        _write_pull_metrics(db, job, crew, outcome)
    except Exception:
        logger.exception("failed to write pull metrics for %s", job.get("ticker"))


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

    job_type = job.get("job_type")
    if job_type and job_type != "ticker_analysis":
        return _run_admin_job(db, job)

    ticker = job["ticker"]
    # 024 — absent means delta, so jobs queued before this feature (and every
    # existing enqueue call site) stay valid with no migration (FR-021).
    mode = job.get("mode") or "delta"
    logger.info("claimed job %s for %s (mode=%s)", job["_id"], ticker, mode)
    crew = crew if crew is not None else Crew(db=db)

    try:
        # earnings-scanner jobs opt in to parallel prefetch (user picked them
        # from a ranked list and is waiting on the result)
        result = crew.run(ticker, parallel_prefetch=bool(job.get("parallel_prefetch")), mode=mode)
        result = sanitize_floats(result)
        write_db(ANALYSES, result, upsert_key="ticker", db=db)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "done", "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )
        _record_pull_metrics(db, job, crew, "done")
        logger.info("%s analysis done (mode=%s signal=%s conviction=%s)",
                    ticker, mode, result.get("signal"), result.get("conviction"))
    except TickerDelistedError as exc:
        logger.warning("%s appears delisted — marking removed_from_market", exc.ticker)
        mark_ticker_removed(exc.ticker, reason=str(exc), db=db)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "failed", "delisted": True, "error": str(exc),
                      "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )
        _record_pull_metrics(db, job, crew, "failed")
    except Exception as exc:
        logger.exception("%s job failed", ticker)
        db[WORK_QUEUE].update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "failed", "delisted": False, "error": str(exc),
                      "completed_at": _utcnow(), "updated_at": _utcnow()}},
        )
        _record_pull_metrics(db, job, crew, "failed")

    return True
