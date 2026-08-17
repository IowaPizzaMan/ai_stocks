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
from datetime import datetime, timezone

import requests
from pymongo.database import Database

from logging_config import get_logger
from tools.db import BENEFICIAL_OWNERSHIP_CACHE, INSTITUTIONAL_CACHE, get_db
from tools.fmp_client import FmpBudgetExceededError, fmp_get

logger = get_logger(__name__)

MAX_FILINGS = 20

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


# ──────────────────────────────────────────────────────────────────────────
# Beneficial ownership (13D/G) — specs/021-stock-page-redesign US7.
# This is the entitled institutional signal on the current FMP plan: the 13F
# `institutional-ownership/latest` endpoint 402s (re-verified 2026-08-16), so
# 5%+ holder filings carry the net bought/sold read instead.
# ──────────────────────────────────────────────────────────────────────────


def normalize_beneficial_filings(raw: list[dict]) -> list[dict]:
    """FMP 13D/G rows → the shape the UI reads (data-model.md §5), newest first.
    FMP returns the numeric fields as strings, hence the explicit coercion."""
    out = []
    for r in raw or []:
        try:
            shares = int(float(r.get("amountBeneficiallyOwned") or 0))
        except (TypeError, ValueError):
            shares = 0
        try:
            pct = float(r.get("percentOfClass") or 0)
        except (TypeError, ValueError):
            pct = 0.0
        out.append({
            "filer": r.get("nameOfReportingPerson") or "unknown",
            "filing_date": str(r.get("filingDate") or "")[:10],
            "shares": shares,
            "pct_of_class": pct,
            "filer_type": r.get("typeOfReportingPerson") or "",
            "url": r.get("url") or "",
        })
    out.sort(key=lambda f: f["filing_date"], reverse=True)
    return out[:MAX_FILINGS]


def derive_beneficial_direction(filings: list[dict]) -> str | None:
    """Are the 5%+ holders adding or trimming? Compares each filer's newest
    disclosed stake against their prior one and takes a majority vote. None
    when no filer has filed twice — a single snapshot shows no direction."""
    by_filer: dict[str, list[dict]] = {}
    for f in filings:
        by_filer.setdefault(f["filer"], []).append(f)

    accumulating = distributing = 0
    for history in by_filer.values():
        if len(history) < 2:
            continue
        ordered = sorted(history, key=lambda f: f["filing_date"])
        latest, prior = ordered[-1], ordered[-2]
        if latest["pct_of_class"] > prior["pct_of_class"]:
            accumulating += 1
        elif latest["pct_of_class"] < prior["pct_of_class"]:
            distributing += 1

    if not accumulating and not distributing:
        return None
    if accumulating > distributing:
        return "accumulating"
    if distributing > accumulating:
        return "distributing"
    return "mixed"


def get_beneficial_ownership(ticker: str, db: Database | None = None) -> dict:
    """Recent 13D/G filings plus the derived direction. Serves cached filings
    when FMP is unavailable or the budget is spent (Principle IV, FR-026)."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    raw: list[dict] | None = None
    stale = False
    try:
        response = fmp_get(f"acquisition-of-beneficial-ownership?symbol={ticker}", db=db)
        raw = response if isinstance(response, list) else []
        db[BENEFICIAL_OWNERSHIP_CACHE].replace_one(
            {"ticker": ticker},
            {"ticker": ticker, "filings": raw, "fetched_at": datetime.now(timezone.utc)},
            upsert=True,
        )
    except FmpBudgetExceededError:
        logger.warning("%s: FMP budget spent — serving cached beneficial ownership", ticker)
        stale = True
    except (requests.HTTPError, requests.RequestException) as exc:
        logger.warning("%s: beneficial ownership fetch failed: %s", ticker, exc)
        stale = True

    if raw is None:
        cached = db[BENEFICIAL_OWNERSHIP_CACHE].find_one({"ticker": ticker}, {"_id": 0})
        raw = (cached or {}).get("filings", [])

    filings = normalize_beneficial_filings(raw)
    return {
        "filings": filings,
        "direction": derive_beneficial_direction(filings),
        "stale": stale,
    }


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
