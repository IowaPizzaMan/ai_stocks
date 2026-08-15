"""Institutional holdings — read-only since specs/017-fmp-migration-admin.

Sourcing history: yfinance's holder tables were the free source (every FMP
13F/institutional endpoint 402/403'd on this key). yfinance is now retired
and the user confirmed 13F is NOT entitled on the paid FMP plan either
(migration-map row 6) — so this module no longer fetches live data at all.
It serves whatever was cached before the migration, read-only, always
flagged `stale: True`. The `fund_holdings` (ETF/fund holdings, entitled) and
`insider_feed` (market-wide insider activity, entitled) datasets are the
intended replacement signals going forward.
"""
from datetime import datetime

from pymongo.database import Database

from logging_config import get_logger
from tools.db import INSTITUTIONAL_CACHE, get_db

logger = get_logger(__name__)

_EMPTY = {
    "top_holders": [], "fund_holders": [], "ownership_pct": None,
    "institutions_count": None, "insiders_pct": None,
    "top10_increasing": 0, "top10_decreasing": 0, "as_of": None,
}


def get_institutional_holdings(ticker: str, db: Database | None = None) -> dict:
    """Read-only: serves the last cached snapshot for this ticker, if any,
    with no live refresh (13F not entitled — migration-map row 6). Always
    carries `stale: True` so callers/UI can render a staleness indicator."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    cached = db[INSTITUTIONAL_CACHE].find_one({"ticker": ticker})
    data = dict(cached["data"]) if cached else dict(_EMPTY)
    data["stale"] = True
    return data


def recent_activity_direction(data: dict) -> str | None:
    """Feed-card flag from the top-10 holder QoQ changes: "buying" when more
    holders grew than trimmed, "selling" for the reverse, "mixed" on a tie,
    None when there's no change data at all (renders as no badge)."""
    increasing = data.get("top10_increasing") or 0
    decreasing = data.get("top10_decreasing") or 0
    if not increasing and not decreasing:
        return None
    if increasing > decreasing:
        return "buying"
    if decreasing > increasing:
        return "selling"
    return "mixed"


def get_recent_13f_changes(since: datetime, universe: list[str] | None = None,
                           db: Database | None = None) -> list[dict]:
    """Market-wide variant for the Phase 7 flow scanner — now reads only
    cached holder data (see get_institutional_holdings), no live fetch."""
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
