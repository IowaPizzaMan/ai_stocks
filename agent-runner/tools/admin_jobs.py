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
from tools.economics import run_economics_pull
from tools.portfolio import run_portfolio_digest

# job_type -> handler(db) -> int (record_count written, for dataset_meta)
JOB_HANDLERS: dict[str, Callable[[Database], int]] = {
    "economics_pull": run_economics_pull,
    # 027-stocks-news-tab-ai-summary — cross-stock AI summary panel. First
    # real user of this dispatch branch besides economics_pull (which
    # actually runs on its own timer, not through work_queue).
    "portfolio_digest": run_portfolio_digest,
}

# job_type -> stale-running recovery minutes override (default 30 if absent)
STALE_MINUTES: dict[str, int] = {
    "economics_pull": 15,  # per contracts/admin-jobs-api.md's registry table
}

# job_type -> dataset_meta dataset name (one entry per job_type; a job that
# writes several collections — e.g. economics_pull — still reports freshness
# as a single dataset, per contracts/admin-jobs-api.md)
#
# economics_pull is deliberately NOT listed here even though its pinned
# dataset name is "economics": run_economics_pull is fail-soft per sub-pull
# (treasury/calendar/indicators/risk-premium each isolated from the others'
# exceptions) and already writes dataset_meta itself with that nuance —
# "failed" only when a sub-pull actually broke. queue_worker._run_admin_job
# writes dataset_meta unconditionally as "success" whenever a handler returns
# without raising, which economics_pull's handler never does by design; adding
# it here would let that generic write silently overwrite a correctly-recorded
# partial failure. See specs/026-macro-market-dashboard/research.md D1.
JOB_DATASETS: dict[str, str] = {}
