"""Market-wide institutional flow scan on its own daily timer (not per-ticker).

Spec: specs/component-specs/agent-runner/institutional_flow_worker.md — implement in Phase 7.
"""
from datetime import datetime


def run_daily_scan_if_due(now: datetime) -> None:
    """No-op until Phase 7 — the daily timer check lives here so main.py's loop is final."""
    return None
