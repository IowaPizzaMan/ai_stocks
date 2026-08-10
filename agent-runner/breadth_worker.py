"""Daily market-breadth refresh on its own timer (not per-ticker).
Spec: specs/component-specs/agent-runner/tools/breadth.md

`get_market_breadth` already computes at most once per UTC day and does the
divergence transition tracking + feed-event emission itself, so this worker
exists only to guarantee that day's computation happens even when no crew run
does. Called every tick from main.py's loop.
"""
from datetime import datetime, timezone

from logging_config import get_logger
from settings import settings
from tools import breadth as breadth_tool
from tools.db import BREADTH_META, get_db

logger = get_logger(__name__)


def _get_meta(db, key: str):
    doc = db[BREADTH_META].find_one({"key": key})
    return doc.get("value") if doc else None


def _set_meta(db, key: str, value) -> None:
    db[BREADTH_META].replace_one({"key": key}, {"key": key, "value": value}, upsert=True)


def _scheduled_due(now: datetime, last_run_at: datetime | None) -> bool:
    if now.hour < settings.breadth_refresh_hour_utc:
        return False
    if last_run_at is None:
        return True
    if last_run_at.tzinfo is None:  # Mongo returns naive UTC datetimes
        last_run_at = last_run_at.replace(tzinfo=timezone.utc)
    return last_run_at.date() < now.date()


def run_daily_breadth_if_due(now: datetime, db=None, refresh=None) -> bool:
    """Returns True when a refresh ran. A failure leaves last_run_at untouched
    so the next tick retries the same day."""
    db = db if db is not None else get_db()
    refresh = refresh if refresh is not None else breadth_tool.get_market_breadth

    if not _scheduled_due(now, _get_meta(db, "last_run_at")):
        return False

    logger.info("starting daily market breadth refresh")
    try:
        result = refresh(db=db)
    except Exception:
        logger.exception("market breadth refresh failed")
        return False

    _set_meta(db, "last_run_at", now)
    logger.info("breadth refresh complete — NYMO %s, divergence %s",
                result["nymo"]["current"], result["divergence"]["type"])
    return True
