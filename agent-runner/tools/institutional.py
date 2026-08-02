"""Institutional holdings via yfinance, cached 90 days in Mongo.
Spec: specs/component-specs/agent-runner/tools/institutional.md

Sourcing (verified 2026-08-02): every FMP 13F/institutional endpoint returns
402/403 on this key (paid tier) — yfinance's holder tables are the free
source: top-10 institutional holders with QoQ pctChange, mutual fund holders,
and the major_holders ownership summary.
"""
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from pymongo.database import Database

from tools.db import INSTITUTIONAL_CACHE, get_db

logger = logging.getLogger(__name__)

CACHE_DAYS = 90  # 13F data updates quarterly


def _records(df) -> list[dict]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")


def _major_holders(df) -> dict:
    """yfinance major_holders: index=Breakdown, single Value column."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    try:
        return {str(k): float(v) for k, v in df.iloc[:, 0].items()}
    except Exception:
        return {}


def get_institutional_holdings(ticker: str, db: Database | None = None) -> dict:
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_DAYS)
    cached = db[INSTITUTIONAL_CACHE].find_one({"ticker": ticker, "fetched_at": {"$gt": cutoff}})
    if cached:
        return cached["data"]

    tk = yf.Ticker(ticker)
    try:
        top_holders = _records(tk.institutional_holders)
        fund_holders = _records(tk.mutualfund_holders)
        major = _major_holders(tk.major_holders)
    except Exception as exc:
        logger.warning("yfinance holders unavailable for %s: %s", ticker, exc)
        top_holders, fund_holders, major = [], [], {}

    increasing = sum(1 for h in top_holders if (h.get("pctChange") or 0) > 0)
    decreasing = sum(1 for h in top_holders if (h.get("pctChange") or 0) < 0)

    data = {
        "top_holders": top_holders,
        "fund_holders": fund_holders,
        "ownership_pct": round(major.get("institutionsPercentHeld", 0) * 100, 2) if major else None,
        "institutions_count": int(major["institutionsCount"]) if major.get("institutionsCount") else None,
        "insiders_pct": round(major.get("insidersPercentHeld", 0) * 100, 2) if major else None,
        "top10_increasing": increasing,
        "top10_decreasing": decreasing,
        "as_of": top_holders[0].get("Date Reported") if top_holders else None,
    }

    db[INSTITUTIONAL_CACHE].replace_one(
        {"ticker": ticker},
        {"ticker": ticker, "data": data, "fetched_at": datetime.now(timezone.utc)},
        upsert=True,
    )
    return data


def get_recent_13f_changes(since: datetime, universe: list[str] | None = None,
                           db: Database | None = None) -> list[dict]:
    """Market-wide variant for the Phase 7 flow scanner: holders whose latest
    reported date falls on/after `since`, across the tracked universe. Reuses
    the per-ticker cache so only stale tickers cost a fetch."""
    db = db if db is not None else get_db()
    if universe is None:
        universe = list(set(db["watchlist"].distinct("ticker")) | set(db["analyses"].distinct("ticker")))

    since_str = since.date().isoformat() if isinstance(since, datetime) else str(since)
    changes = []
    for ticker in sorted(set(universe)):
        data = get_institutional_holdings(ticker, db=db)
        for holder in data.get("top_holders", []):
            reported = holder.get("Date Reported") or ""
            if reported >= since_str and (holder.get("pctChange") or 0) != 0:
                changes.append({**holder, "ticker": ticker})
    return changes
