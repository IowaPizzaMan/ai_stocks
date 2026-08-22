"""Spec: specs/component-specs/backend/routers/sectors.md

Sector-level rollups of the latest analysis per ticker. The heavy lift
(latest-per-ticker) runs in Mongo; the per-sector rollup happens in Python —
it's one row per ticker at that point, and this keeps the counting logic
plain enough to read.

Also serves the sector ETF comparison chart (specs/028-dashboard-tweaks-batch
US5) — read-only over price_history, written by the agent-runner's
sector_etf_pull admin job (agent-runner/tools/sector_etfs.py). This router
never calls a provider itself; POST /etf-series/refresh only enqueues that
job, deduped like every other refresh endpoint in this batch.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

import price_store
from db import ANALYSES, TICKER_INDEX, WORK_QUEUE
from deps import db_dependency
from routers.analysis import UNCLASSIFIED, get_sector_analyses

router = APIRouter(prefix="/sectors", tags=["sectors"])

_SIGNAL_RANK = {"bullish": 2, "neutral": 1, "bearish": 0}
_CONVICTION_RANK = {"high": 2, "medium": 1, "low": 0}

# Hand-synced with agent-runner/tools/sector_etfs.py::SECTOR_ETF_LABELS
# (Principle VI — the two services share no package).
SECTOR_ETF_LABELS: dict[str, str] = {
    "XLC": "Communication Services",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLV": "Health Care",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLK": "Technology",
    "XLU": "Utilities",
}

# window -> days back from the series' own latest stored date (not "today" —
# a pull can be a day or two stale, and slicing against the data's own max
# keeps the chart honest about what it actually holds).
_WINDOW_DAYS = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}


@router.get("/etf-series")
def get_etf_series(
    window: str = Query(default="6m"),
    db=Depends(db_dependency),
):
    if window not in _WINDOW_DAYS:
        raise HTTPException(
            status_code=422, detail=f"window must be one of {sorted(_WINDOW_DAYS)}"
        )
    days = _WINDOW_DAYS[window]

    series = []
    for ticker, label in SECTOR_ETF_LABELS.items():
        df, _meta = price_store.get_series(ticker, refresh="none", db=db)
        if df.empty:
            series.append({"ticker": ticker, "label": label, "bars": [], "partial": True})
            continue

        cutoff = df.index.max() - timedelta(days=days)
        sliced = df[df.index >= cutoff]
        # Partial when history doesn't reach back to the window's start —
        # judged against the *stored* span, not the slice, since a series
        # that starts later than the cutoff is exactly the case to flag.
        partial = df.index.min() > cutoff

        bars = [
            {"date": idx.strftime("%Y-%m-%d"), "close": round(float(row["Close"]), 4)}
            for idx, row in sliced.iterrows()
            if row["Close"] == row["Close"]  # drop NaN closes
        ]
        series.append({"ticker": ticker, "label": label, "bars": bars, "partial": partial})

    return {"window": window, "series": series, "as_of": datetime.now(timezone.utc).isoformat()}


@router.post("/etf-series/refresh")
def refresh_etf_series(db=Depends(db_dependency)):
    existing = db[WORK_QUEUE].find_one(
        {"job_type": "sector_etf_pull", "status": {"$in": ["pending", "running"]}}
    )
    if existing:
        return {"status": "already_queued", "job_id": str(existing["_id"])}

    now = datetime.now(timezone.utc)
    result = db[WORK_QUEUE].insert_one({
        "job_type": "sector_etf_pull",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    })
    return {"status": "enqueued", "job_id": str(result.inserted_id)}


@router.get("")
def get_sectors(db=Depends(db_dependency)):
    """029-company-profile-tweaks (FR-026): sector is read from ticker_index
    (the company profile's value), not analyses.sector — nothing has ever
    written that field (KNOWN_ISSUES.md's first open bug: this endpoint's
    $match on it always matched zero documents). Latest-per-ticker still runs
    in Mongo; the sector join and rollup happen in Python, same design as
    before (module docstring)."""
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$ticker", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0, "ticker": 1, "signal": 1, "conviction": 1}},
    ]
    latest = list(db[ANALYSES].aggregate(pipeline))
    if not latest:
        return []

    sector_by_ticker = {
        d["ticker"]: d.get("sector")
        for d in db[TICKER_INDEX].find(
            {"ticker": {"$in": [doc["ticker"] for doc in latest]}}, {"_id": 0, "ticker": 1, "sector": 1}
        )
    }

    sectors: dict[str, dict] = {}
    for doc in latest:
        sector = sector_by_ticker.get(doc["ticker"]) or UNCLASSIFIED
        s = sectors.setdefault(sector, {
            "sector": sector,
            "bullish_count": 0, "bearish_count": 0, "neutral_count": 0,
            "ticker_count": 0, "_best": None,
        })
        if f"{doc.get('signal')}_count" in s:
            s[f"{doc['signal']}_count"] += 1
        s["ticker_count"] += 1
        # top ticker = most bullish, conviction breaking ties
        key = (_SIGNAL_RANK.get(doc["signal"], 0), _CONVICTION_RANK.get(doc["conviction"], 0))
        if s["_best"] is None or key > s["_best"][0]:
            s["_best"] = (key, doc["ticker"])

    # Unclassified sorts last regardless of alphabetical order (FR-027) —
    # it's "awaiting a pull", not a sector name to alphabetize among others.
    ordered = sorted(
        sectors.values(), key=lambda x: (x["sector"] == UNCLASSIFIED, x["sector"])
    )
    out = []
    for s in ordered:
        best = s.pop("_best")
        s["top_ticker"] = best[1] if best else None
        out.append(s)
    return out


@router.get("/{sector}")
def get_sector_detail(sector: str, db=Depends(db_dependency)):
    """Alias of GET /analysis/sector/{sector} for semantic URL clarity."""
    return get_sector_analyses(sector, db=db)
