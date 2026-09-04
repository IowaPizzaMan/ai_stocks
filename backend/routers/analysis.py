"""Spec: specs/component-specs/backend/routers/analysis.md

specs/037-stocks-conviction-and-activity (contracts/feed-ordering.md): the
feed's sort is (conviction_rank desc, ticker asc), not recency — see
get_feed() below.
"""
import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends

from db import ANALYSES, TICKER_INDEX
from deps import db_dependency

router = APIRouter(prefix="/analysis", tags=["analysis"])

# 029-company-profile-tweaks (FR-027) — the reserved bucket name GET /sectors
# assigns to tracked stocks with no profile sector (backend/routers/sectors.py
# is the canonical definition; kept in sync here). It is a *computed* label,
# never a literal value stored on any ticker_index document, so a plain
# {"sector": "Unclassified"} query would always resolve to zero tickers —
# _resolve_by_sector special-cases it to match how the rollup buckets stocks
# (missing/empty sector), which is what makes FR-026a's "a sector's rollup
# count equals its filtered grid count" hold for this bucket too.
UNCLASSIFIED = "Unclassified"


def _resolve_tickers(db, field: str, value: str) -> list[str]:
    return [d["ticker"] for d in db[TICKER_INDEX].find({field: value}, {"_id": 0, "ticker": 1})]


def _resolve_by_sector(db, value: str) -> list[str]:
    query = {"sector": {"$in": [None, ""]}} if value == UNCLASSIFIED else {"sector": value}
    return [d["ticker"] for d in db[TICKER_INDEX].find(query, {"_id": 0, "ticker": 1})]


@router.get("/feed")
def get_feed(
    page: int = 1,
    page_size: int = 20,
    ticker: str | None = None,
    signal: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    conviction: str | None = None,
    sentiment: Literal["liked", "disliked"] | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    db=Depends(db_dependency),
):
    filter: dict = {}
    # 028-dashboard-tweaks-batch US3 (FR-009, R11) — two-step, not a $lookup:
    # resolve matching tickers from ticker_index, then constrain analyses by
    # $in. Combined via $and rather than overwriting one another, since every
    # condition here constrains the same `ticker` field.
    #
    # 029-company-profile-tweaks US5 (contracts/sector-and-industry.md): sector
    # and industry now join the same list, reusing this exact pattern —
    # sector is sourced from ticker_index (the company profile's value, the
    # system's single sector source per FR-026), not from analyses.sector
    # (which nothing has ever written — KNOWN_ISSUES.md's first open bug).
    ticker_conditions = []
    if ticker:
        # substring match so partial typing narrows as-you-go (FilterBar search)
        ticker_conditions.append({"ticker": {"$regex": re.escape(ticker), "$options": "i"}})
    if sentiment:
        tagged = _resolve_tickers(db, "sentiment", sentiment)
        # An empty resolved set must yield $in: [] (matches nothing), never be
        # skipped — skipping it would silently fall back to the unfiltered feed.
        ticker_conditions.append({"ticker": {"$in": tagged}})
    if sector:
        ticker_conditions.append({"ticker": {"$in": _resolve_by_sector(db, sector)}})
    if industry:
        ticker_conditions.append({"ticker": {"$in": _resolve_tickers(db, "industry", industry)}})

    if len(ticker_conditions) == 1:
        filter.update(ticker_conditions[0])
    elif len(ticker_conditions) > 1:
        filter["$and"] = ticker_conditions

    if signal:
        filter["signal"] = signal
    if conviction:
        filter["conviction"] = conviction
    if from_date or to_date:
        filter["timestamp"] = {}
        if from_date:
            filter["timestamp"]["$gte"] = from_date
        if to_date:
            filter["timestamp"]["$lte"] = to_date

    # sub_reports are far too large for the feed — project them out
    projection = {"_id": 0, "sub_reports": 0}
    total = db[ANALYSES].count_documents(filter)
    # 037-stocks-conviction-and-activity (contracts/feed-ordering.md) —
    # conviction descending, then ticker ascending. `analyses` carries a
    # unique index on `ticker`, so this is a *total* order: any client-side
    # signal-group subset of it is already conviction-then-A→Z, and skip/
    # limit paging over it means "Load more" strictly appends (no reflow of
    # already-rendered tiles). Sorting the string `conviction` directly would
    # be wrong (alphabetical: high < low < medium) — conviction_rank exists
    # precisely to avoid that.
    items = list(
        db[ANALYSES].find(filter, projection)
        .sort([("conviction_rank", -1), ("ticker", 1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    # 029-company-profile-tweaks US3 (FR-021a) — one ticker_index query for
    # this page's tickers, not one per item, so a 60-tile grid costs one
    # extra query rather than 60.
    if items:
        idx_by_ticker = {
            d["ticker"]: d
            for d in db[TICKER_INDEX].find(
                {"ticker": {"$in": [i["ticker"] for i in items]}},
                {"_id": 0, "ticker": 1, "name": 1, "logo_url": 1},
            )
        }
        for item in items:
            idx = idx_by_ticker.get(item["ticker"], {})
            item["name"] = idx.get("name")
            item["logo_url"] = idx.get("logo_url")

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sector/{sector}")
def get_sector_analyses(sector: str, db=Depends(db_dependency)):
    """Most recent analysis per ticker within a sector.

    029-company-profile-tweaks US5 (FR-026): sector is resolved from
    ticker_index (the company profile's value) rather than analyses.sector,
    which nothing has ever written (KNOWN_ISSUES.md's first open bug) — same
    two-step join as GET /analysis/feed. `sector=Unclassified` resolves via
    the same missing/empty-sector special case (see UNCLASSIFIED)."""
    tickers = _resolve_by_sector(db, sector)
    if not tickers:
        return []
    pipeline = [
        {"$match": {"ticker": {"$in": tickers}}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$ticker", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0, "sub_reports": 0}},
    ]
    return list(db[ANALYSES].aggregate(pipeline))


@router.get("/{ticker}")
def get_ticker_analysis(ticker: str, db=Depends(db_dependency)):
    return db[ANALYSES].find_one({"ticker": ticker.upper()}, {"_id": 0})
