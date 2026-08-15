"""Independent per-sector macro refresh, decoupled from ticker analysis.
Spec: specs/020-surface-macro-ui, specs/component-specs/agent-runner/macro_worker.md

Staleness-driven, not meta-key-driven: each sweep (throttled to at most once
per hour, in-process — a single agent-runner process per compose deployment)
enumerates active sectors from ticker_index and refreshes any whose
macro_analysis_cache read is missing or older than macro_analyst.CACHE_DAYS.
Called every tick from main.py's loop, alongside the breadth worker.
"""
from datetime import datetime, timedelta, timezone

from agents import macro_analyst
from logging_config import get_logger
from tools import macro as macro_tool
from tools.db import MACRO_ANALYSIS_CACHE, TICKER_INDEX, get_db

logger = get_logger(__name__)

SWEEP_THROTTLE = timedelta(hours=1)

_last_sweep_at: datetime | None = None


def _active_sectors(db) -> list[str]:
    return db[TICKER_INDEX].distinct(
        "sector", {"sector": {"$nin": [None, ""]}, "status": {"$ne": "removed_from_market"}}
    )


def _is_due(db, sector: str, now: datetime) -> bool:
    doc = db[MACRO_ANALYSIS_CACHE].find_one({"sector": sector})
    if doc is None:
        return True
    computed_at = doc["computed_at"]
    if computed_at.tzinfo is None:  # Mongo returns naive UTC datetimes
        computed_at = computed_at.replace(tzinfo=timezone.utc)
    return computed_at < now - timedelta(days=macro_analyst.CACHE_DAYS)


def run_macro_refresh_if_due(now: datetime, db=None, client=None,
                             get_macro_data=None, get_yield_curve_status=None) -> int:
    """Returns the number of sectors refreshed this call (0 on a throttled or
    no-op tick). Never raises — one sector's failure is logged and skipped;
    macro_analyst.run() persists each successful sector itself."""
    global _last_sweep_at
    if _last_sweep_at is not None and now - _last_sweep_at < SWEEP_THROTTLE:
        return 0
    _last_sweep_at = now

    db = db if db is not None else get_db()
    get_macro_data = get_macro_data or macro_tool.get_macro_data
    get_yield_curve_status = get_yield_curve_status or macro_tool.get_yield_curve_status

    due = [s for s in _active_sectors(db) if _is_due(db, s, now)]
    if not due:
        return 0

    context = {"macro": get_macro_data(db=db), "yield_curve": get_yield_curve_status(db=db)}

    refreshed = 0
    for sector in due:
        try:
            macro_analyst.run(sector, context, client=client, db=db)
            refreshed += 1
        except Exception:
            logger.exception("macro refresh failed for sector %s", sector)

    logger.info("macro worker: refreshed %s/%s due sectors", refreshed, len(due))
    return refreshed
