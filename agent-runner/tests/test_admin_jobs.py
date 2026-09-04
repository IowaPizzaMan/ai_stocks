"""tools/admin_jobs.py — the work_queue job_type -> handler registry.
Spec: specs/017-fmp-migration-admin/contracts/admin-jobs-api.md
"""
from tools import admin_jobs, congress as congress_tool, market_movers, news_pull, sector_etfs, strategy_signals


def test_028_batch_jobs_registered_in_job_handlers():
    """specs/028-dashboard-tweaks-batch US4/US5/US6."""
    assert admin_jobs.JOB_HANDLERS["market_movers_pull"] is market_movers.run_market_movers_pull
    assert admin_jobs.JOB_HANDLERS["sector_etf_pull"] is sector_etfs.run_sector_etf_pull
    assert admin_jobs.JOB_HANDLERS["congress_trades_pull"] is congress_tool.run_congress_trades_pull


def test_strategy_signals_refresh_registered_in_job_handlers():
    """specs/032-weekly-strategy-picks."""
    assert (
        admin_jobs.JOB_HANDLERS["strategy_signals_refresh"]
        is strategy_signals.run_strategy_signals_refresh
    )
    assert admin_jobs.STALE_MINUTES["strategy_signals_refresh"] == 15


def test_market_news_pull_registered_in_job_handlers():
    """specs/035-chat-and-news-upgrade US2."""
    assert admin_jobs.JOB_HANDLERS["market_news_pull"] is news_pull.run_market_news_pull
    assert admin_jobs.STALE_MINUTES["market_news_pull"] == 20
    assert admin_jobs.JOB_DATASETS["market_news_pull"] == "news_articles"
