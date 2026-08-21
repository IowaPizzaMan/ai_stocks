"""Daily economics-data refresh on its own timer (not per-ticker).
Spec: specs/026-macro-market-dashboard/research.md D1

Mirrors breadth_worker.py's scheduling shape exactly, with one deliberate
difference: `tools.economics.run_economics_pull` is fail-soft *per sub-pull*
(treasury/calendar/indicators/risk-premium each isolated from the others'
exceptions) and never raises, so — unlike breadth, which either fully
succeeds or fully crashes — this worker can't distinguish "nothing landed
today" from "everything landed" by catching an exception. It marks the day
attempted either way rather than retry-storming on a bad day; each sub-pull's
own incremental/gap-healing logic (treasury resumes from the last stored
session, the calendar re-fetches its rolling window) naturally catches up
whatever a down day missed once the provider recovers. Freshness for readers
comes from `dataset_meta`, written by `run_economics_pull` itself — not from
this worker's own scheduling marker.
"""
from datetime import datetime, timezone

from logging_config import get_logger
from settings import settings
from tools import economics as economics_tool
from tools.db import ECONOMICS_META, get_db

logger = get_logger(__name__)


def _get_meta(db, key: str):
    doc = db[ECONOMICS_META].find_one({"key": key})
    return doc.get("value") if doc else None


def _set_meta(db, key: str, value) -> None:
    db[ECONOMICS_META].replace_one({"key": key}, {"key": key, "value": value}, upsert=True)


def _scheduled_due(now: datetime, last_run_at: datetime | None) -> bool:
    if now.hour < settings.economics_refresh_hour_utc:
        return False
    if last_run_at is None:
        return True
    if last_run_at.tzinfo is None:  # Mongo returns naive UTC datetimes
        last_run_at = last_run_at.replace(tzinfo=timezone.utc)
    return last_run_at.date() < now.date()


def run_daily_economics_if_due(now: datetime, db=None, refresh=None) -> bool:
    """Returns True when a refresh ran. A hard crash (refresh itself raising,
    as opposed to a sub-pull failing internally) leaves last_run_at untouched
    so the next tick retries the same day."""
    db = db if db is not None else get_db()
    refresh = refresh if refresh is not None else economics_tool.run_economics_pull

    if not _scheduled_due(now, _get_meta(db, "last_run_at")):
        return False

    logger.info("starting daily economics refresh")
    try:
        record_count = refresh(db=db)
    except Exception:
        logger.exception("economics refresh failed")
        return False

    _set_meta(db, "last_run_at", now)
    logger.info("economics refresh complete — %s records written", record_count)
    return True
