"""FMP financials + earnings/estimates data, cached in Mongo.
Spec: specs/component-specs/agent-runner/tools/financials.md
"""
from datetime import datetime, timedelta, timezone

import requests
from pymongo.database import Database

from logging_config import get_logger
from tools.db import FINANCIALS_CACHE, get_db
from tools.fmp_client import FmpBudgetExceededError, fmp_get

logger = get_logger(__name__)

CACHE_DAYS = 90

# key -> path template ("essential" no longer gates the fetch — the shared
# fmp_client throttle/budget guard in tools/fmp_client.py handles that
# uniformly now; every endpoint here degrades to [] on 402/403/budget-exceeded
# so the crew run always proceeds)
ENDPOINTS = {
    "income_annual": "income-statement?symbol={t}&period=annual&limit=4",
    "income_quarterly": "income-statement?symbol={t}&period=quarter&limit=4",
    "balance_annual": "balance-sheet-statement?symbol={t}&period=annual&limit=4",
    "cashflow_annual": "cash-flow-statement?symbol={t}&period=annual&limit=4",
    "ratios": "ratios?symbol={t}&period=annual&limit=4",
    "key_metrics": "key-metrics?symbol={t}&period=annual&limit=4",
    "growth": "income-statement-growth?symbol={t}&limit=4",
}


def _fetch_statement(ticker: str, key: str, db: Database | None) -> list | dict:
    """One FMP statement fetch, degraded to [] on the two temporary
    conditions (plan restriction, budget cap) so the crew run proceeds."""
    try:
        return fmp_get(ENDPOINTS[key].format(t=ticker), db=db)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status not in (402, 403):
            raise
        # this plan covers fundamentals for only a subset of symbols
        # (verified 2026-08-02: AAPL 200, APP 402 on the same day/key) —
        # degrade to empty so the crew run proceeds
        logger.info("FMP %s for %s/%s — not covered on this plan, skipping", status, ticker, key)
        return []
    except FmpBudgetExceededError:
        logger.warning("FMP daily soft cap exceeded — skipping %s for %s", key, ticker)
        return []


def get_financials(ticker: str, db: Database | None = None) -> dict:
    """Income/balance/cashflow/ratios for a ticker, served from the 90-day
    Mongo cache when possible (~7 FMP calls on a cold fetch, 0 after).

    A cached statement type that is empty because an earlier fetch hit a
    temporary condition (402/403 plan restriction or budget cap) is NOT
    settled: it's re-fetched on every call until FMP answers 200
    (specs/018-fix-financials-cache-gap — the BSX bug, where an all-402
    fetch was served as "no data" for the rest of the 90-day window).
    Confirmed keys are never re-fetched inside the window, and a partial
    retry deliberately leaves fetched_at alone so the window doesn't slide."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_DAYS)
    cached = db[FINANCIALS_CACHE].find_one({"ticker": ticker, "fetched_at": {"$gt": cutoff}})
    if cached:
        data = cached["data"]
        retry_keys = [k for k in ENDPOINTS if not data.get(k)]
        if not retry_keys:
            return data
        for key in retry_keys:
            data[key] = _fetch_statement(ticker, key, db)
        db[FINANCIALS_CACHE].update_one({"ticker": ticker}, {"$set": {"data": data}})
        return data

    data = {key: _fetch_statement(ticker, key, db) for key in ENDPOINTS}
    db[FINANCIALS_CACHE].replace_one(
        {"ticker": ticker},
        {"ticker": ticker, "data": data, "fetched_at": datetime.now(timezone.utc)},
        upsert=True,
    )
    return data


def get_earnings_data(ticker: str, db: Database | None = None) -> dict:
    """Earnings snapshot for the fundamental analyst: recent/upcoming dates,
    forward estimates, and analyst grade activity — sourced from FMP.
    Individual sections degrade to empty on failure so one gap doesn't sink
    the whole report.

    eps_trend/eps_revisions have no FMP equivalent on this plan (documented
    drop — specs/017-fmp-migration-admin/contracts/fmp-migration-map.md row
    5) and are kept as empty for shape compatibility with existing callers
    (agents/fundamental_analyst.py reads earnings.get("eps_trend"))."""
    def section(fn):
        try:
            result = fn()
            return result if result is not None else []
        except Exception as exc:
            logger.info("earnings section unavailable for %s: %s", ticker, exc)
            return []

    return {
        "earnings_dates": section(lambda: fmp_get(f"earnings?symbol={ticker}&limit=8", db=db)),
        "eps_trend": {},
        "eps_revisions": [],
        "forward_estimates": section(lambda: fmp_get(f"analyst-estimates?symbol={ticker}&limit=4", db=db)),
        "analyst_recs": section(lambda: fmp_get(f"grades?symbol={ticker}&limit=10", db=db)),
    }
