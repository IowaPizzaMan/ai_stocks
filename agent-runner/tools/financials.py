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

FMP_BASE = "https://financialmodelingprep.com/api/"
CACHE_DAYS = 90

# FMP free tier: 250 calls/day. Warn near the ceiling; drop nice-to-have
# endpoints just under it so essential statements still get through.
WARN_AT = 200
SKIP_NON_ESSENTIAL_AT = 240

# key -> (path template, essential)
ENDPOINTS = {
    "income_annual": ("v3/income-statement/{t}?period=annual&limit=4", True),
    "income_quarterly": ("v3/income-statement/{t}?period=quarter&limit=8", True),
    "balance_annual": ("v3/balance-sheet-statement/{t}?period=annual&limit=4", True),
    "cashflow_annual": ("v3/cash-flow-statement/{t}?period=annual&limit=4", True),
    "ratios": ("v3/ratios/{t}?period=annual&limit=4", False),
    "key_metrics": ("v3/key-metrics/{t}?period=annual&limit=4", False),
    "growth": ("v3/income-statement-growth/{t}", False),
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
        data[key] = fmp_get(template.format(t=ticker))

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
