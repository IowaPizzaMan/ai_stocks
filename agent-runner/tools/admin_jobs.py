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
from tools.news_pull import run_market_news_pull
from tools.screener import run_screener_refresh
from tools.sector_etfs import run_sector_etf_pull
from tools.strategy_signals import run_strategy_signals_refresh

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
    # 031-semantic-layer-chat — full-universe recompute of the flat `screener`
    # collection chat reads from. Also triggered per-ticker via
    # tools.screener.refresh_one() right after that ticker's own prefetch
    # (queue_worker.py), so this admin job is for a manual/scheduled full
    # rebuild rather than the only way signals get refreshed.
    "screener_refresh": run_screener_refresh,
    # 032-weekly-strategy-picks — full-universe recompute of the `strategy_signals`
    # collection backend/semantic/strategy_picks.py reads from. Unlike
    # screener_refresh, there is no per-ticker trigger for this one yet (The
    # Strat / Gap Analysis aren't in AnalysisCrew's per-ticker hot path the
    # way screener signals are) — this admin job is the only way it's kept
    # fresh, so it should run on a recurring schedule.
    "strategy_signals_refresh": run_strategy_signals_refresh,
    # 035-chat-and-news-upgrade — implements the job type 017's registry
    # table reserved but never built (KNOWN_ISSUES.md, now resolved).
    "market_news_pull": run_market_news_pull,
}

# job_type -> stale-running recovery minutes override (default 30 if absent)
STALE_MINUTES: dict[str, int] = {
    "economics_pull": 15,  # per contracts/admin-jobs-api.md's registry table
    "market_movers_pull": 10,  # per 017's registry table
    "sector_etf_pull": 10,  # matches market_movers_pull — same order of I/O
    "congress_trades_pull": 15,  # per 017's registry table
    "screener_refresh": 10,  # single pass over price_history, same order as market_movers_pull
    # 032-weekly-strategy-picks — same single-pass-over-price_history shape as
    # screener_refresh, but each ticker now runs two rule-engine skills
    # (multi-timeframe resample + pattern detection) instead of one flat
    # signal computation, so it's budgeted closer to congress_trades_pull.
    "strategy_signals_refresh": 15,
    # 035-chat-and-news-upgrade — three sequential paged feeds per run, more
    # I/O than congress_trades_pull's single call.
    "market_news_pull": 20,
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
    # 035-chat-and-news-upgrade — like congress_trades_pull above, a single
    # total count across the three feeds accurately reflects a partial
    # success (one feed budget-exhausted, others landed) as a real success,
    # not a failure — news_pull.py never raises for a per-feed provider
    # failure, only reports what it actually ingested. Distinct from the
    # per-feed backfill checkpoints in dataset_meta (keyed news_<source_type>,
    # written directly by news_pull.py, not through this generic path).
    "market_news_pull": "news_articles",
}
