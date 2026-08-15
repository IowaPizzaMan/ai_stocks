"""Registry of non-ticker ("admin") work_queue job handlers.
Spec: specs/017-fmp-migration-admin/contracts/admin-jobs-api.md

queue_worker.py dispatches on work_queue's `job_type` field through
JOB_HANDLERS. Populated incrementally as each admin job is implemented
(breadth_refresh / earnings_calendar_scan / fmp_entitlement_probe /
fund_holdings_pull / sector_performance_pull / market_movers_pull /
economics_pull / congress_trades_pull / insider_feed_pull /
market_news_pull) — see the registry table in the contract above.

Deliberately NOT shared with backend/routers/admin.py's ADMIN_JOBS constant
(job descriptions for the UI) — the two are duplicated small constants per
constitution Principle V/VI, kept in sync by hand against the same contract.
"""
from typing import Callable

from pymongo.database import Database

# job_type -> handler(db) -> int (record_count written, for dataset_meta)
JOB_HANDLERS: dict[str, Callable[[Database], int]] = {}

# job_type -> stale-running recovery minutes override (default 30 if absent)
STALE_MINUTES: dict[str, int] = {}

# job_type -> dataset_meta dataset name (one entry per job_type; a job that
# writes several collections — e.g. economics_pull — still reports freshness
# as a single dataset, per contracts/admin-jobs-api.md)
JOB_DATASETS: dict[str, str] = {}
