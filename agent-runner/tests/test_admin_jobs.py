"""tools/admin_jobs.py — the work_queue job_type -> handler registry.
Spec: specs/017-fmp-migration-admin/contracts/admin-jobs-api.md
"""
from tools import admin_jobs, congress as congress_tool, market_movers, sector_etfs


def test_028_batch_jobs_registered_in_job_handlers():
    """specs/028-dashboard-tweaks-batch US4/US5/US6."""
    assert admin_jobs.JOB_HANDLERS["market_movers_pull"] is market_movers.run_market_movers_pull
    assert admin_jobs.JOB_HANDLERS["sector_etf_pull"] is sector_etfs.run_sector_etf_pull
    assert admin_jobs.JOB_HANDLERS["congress_trades_pull"] is congress_tool.run_congress_trades_pull
