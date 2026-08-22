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
from tools.congress import run_congress_trades_pull
from tools.economics import run_economics_pull
from tools.market_movers import run_market_movers_pull
from tools.sector_etfs import run_sector_etf_pull

# job_type -> handler(db) -> int (record_count written, for dataset_meta)
JOB_HANDLERS: dict[str, Callable[[Database], int]] = {
    "economics_pull": run_economics_pull,
    # 028-dashboard-tweaks-batch US6 — implements only the "actives" category
    # of 017's registered job; gainers/losers remain unwritten (R9).
    "market_movers_pull": run_market_movers_pull,
    # 028-dashboard-tweaks-batch US5 — not in 017's registry (that spec's
    # sector_performance_pull is a different dataset, R5); reuses price_store
    # unchanged for the 11 sector ETFs.
    "sector_etf_pull": run_sector_etf_pull,
    # 028-dashboard-tweaks-batch US4 — implements 017's already-registered
    # job, reusing its pinned congress_trades schema (R7).
    "congress_trades_pull": run_congress_trades_pull,
}

# job_type -> stale-running recovery minutes override (default 30 if absent)
STALE_MINUTES: dict[str, int] = {
    "economics_pull": 15,  # per contracts/admin-jobs-api.md's registry table
    "market_movers_pull": 10,  # per 017's registry table
    "sector_etf_pull": 10,  # matches market_movers_pull — same order of I/O
    "congress_trades_pull": 15,  # per 017's registry table
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
JOB_DATASETS: dict[str, str] = {
    # 028-dashboard-tweaks-batch US6 — simple atomic-per-run handler (either
    # the fetch succeeds and rows are written, or it raises before writing
    # anything), so the generic success/failed write is accurate here, unlike
    # economics_pull's per-sub-pull nuance above.
    "market_movers_pull": "market_movers",
    # 028-dashboard-tweaks-batch US4 — a single record_count already reflects
    # a one-chamber-failed partial success correctly; per 017's registry table.
    "congress_trades_pull": "congress_trades",
}
