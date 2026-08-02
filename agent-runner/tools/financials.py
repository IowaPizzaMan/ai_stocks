"""FMP financials + yfinance earnings data, cached in Mongo.
Spec: specs/component-specs/agent-runner/tools/financials.md
"""
import logging
from datetime import datetime, timedelta, timezone

import requests
import yfinance as yf
from pymongo.database import Database

from settings import settings
from tools.db import FINANCIALS_CACHE, get_db, track_fmp_call

logger = logging.getLogger(__name__)

# The legacy /api/v3 endpoints 403 for accounts created after FMP's 2025
# migration — this key only works against the "stable" API.
FMP_BASE = "https://financialmodelingprep.com/stable/"
CACHE_DAYS = 90

# FMP free tier: 250 calls/day. Warn near the ceiling; drop nice-to-have
# endpoints just under it so essential statements still get through.
WARN_AT = 200
SKIP_NON_ESSENTIAL_AT = 240

# key -> (path template, essential)
ENDPOINTS = {
    "income_annual": ("income-statement?symbol={t}&period=annual&limit=4", True),
    # free tier 402s quarterly history deeper than ~4 periods (limit=8 rejected)
    "income_quarterly": ("income-statement?symbol={t}&period=quarter&limit=4", True),
    "balance_annual": ("balance-sheet-statement?symbol={t}&period=annual&limit=4", True),
    "cashflow_annual": ("cash-flow-statement?symbol={t}&period=annual&limit=4", True),
    "ratios": ("ratios?symbol={t}&period=annual&limit=4", False),
    "key_metrics": ("key-metrics?symbol={t}&period=annual&limit=4", False),
    "growth": ("income-statement-growth?symbol={t}&limit=4", False),
}


def fmp_get(path: str) -> list | dict:
    sep = "&" if "?" in path else "?"
    url = f"{FMP_BASE}{path}{sep}apikey={settings.fmp_api_key}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def get_financials(ticker: str, db: Database | None = None) -> dict:
    """Income/balance/cashflow/ratios for a ticker, served from the 90-day
    Mongo cache when possible (~7 FMP calls on a cold fetch, 0 after)."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_DAYS)
    cached = db[FINANCIALS_CACHE].find_one({"ticker": ticker, "fetched_at": {"$gt": cutoff}})
    if cached:
        return cached["data"]

    data = {}
    for key, (template, essential) in ENDPOINTS.items():
        count = track_fmp_call(db=db)
        if count >= SKIP_NON_ESSENTIAL_AT and not essential:
            logger.warning("FMP quota nearly exhausted (%s calls today) — skipping %s for %s", count, key, ticker)
            data[key] = []
            continue
        if count >= WARN_AT:
            logger.warning("FMP daily usage at %s calls (free tier: 250)", count)
        try:
            data[key] = fmp_get(template.format(t=ticker))
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in (402, 403):
                raise
            # free tier covers fundamentals for only a subset of symbols
            # (verified 2026-08-02: AAPL 200, APP 402 on the same day/key) —
            # degrade to empty so the crew run proceeds on yfinance data
            logger.info("FMP %s for %s/%s — not covered on this plan, skipping", status, ticker, key)
            data[key] = []

    db[FINANCIALS_CACHE].replace_one(
        {"ticker": ticker},
        {"ticker": ticker, "data": data, "fetched_at": datetime.now(timezone.utc)},
        upsert=True,
    )
    return data


def get_earnings_data(ticker: str) -> dict:
    """Earnings history, estimates, and analyst recs via yfinance (no rate limit).
    Individual sections degrade to empty on failure — yfinance endpoints are
    per-ticker flaky and one gap shouldn't sink the whole report."""
    tk = yf.Ticker(ticker)

    def section(fn):
        try:
            result = fn()
            return result if result is not None else []
        except Exception as exc:
            logger.info("earnings section unavailable for %s: %s", ticker, exc)
            return []

    return {
        "earnings_dates": section(
            lambda: tk.get_earnings_dates(limit=8).reset_index().to_dict(orient="records")
        ),
        "eps_trend": section(lambda: tk.get_eps_trend().to_dict()),
        "eps_revisions": section(lambda: tk.get_eps_revisions().to_dict()),
        "forward_estimates": section(lambda: tk.get_earnings_estimate().to_dict()),
        "analyst_recs": section(lambda: tk.get_recommendations().to_dict(orient="records")),
    }
