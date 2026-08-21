"""Treasury/calendar/indicator/risk-premium pulls for the Macro dashboard.
Spec: specs/026-macro-market-dashboard/data-model.md, research.md D1-D6

Implements the `economics_pull` admin job that specs/017-fmp-migration-admin
reserved (job registry, dataset name, all four collections) but never wrote a
handler for. Four independent sub-pulls feed one `dataset_meta` entry
("economics", per 017's contract), but each sub-pull is individually fail-soft
— one provider hiccup degrades that collection alone, not the whole run
(constitution IV, FR-027's isolation requirement pushed down to the data layer).

`treasury_rates` is the only one of the four that's a maintained store rather
than a refreshed-in-place cache: it backfills once (~2 years, chunked — the
provider truncates any request wider than ~3 months to its most recent ~62
rows, research D2) and then extends by one call a day, resuming from the last
stored session rather than assuming yesterday (FR-017b).
"""
from datetime import date, datetime, timedelta, timezone

import requests
from pymongo.database import Database

from logging_config import get_logger
from tools.db import (
    DATASET_META,
    ECONOMIC_CALENDAR_EVENTS,
    ECONOMIC_INDICATORS,
    MARKET_RISK_PREMIUM,
    TREASURY_RATES,
    write_dataset_meta,
)
from tools.fmp_client import FmpBudgetExceededError, fmp_get

logger = get_logger(__name__)

BACKFILL_DATASET = "economics_backfill"
BACKFILL_TOTAL_DAYS = 730  # ~2 years, per FR-017a
BACKFILL_WINDOW_DAYS = 90  # provider truncates wider ranges (research D2)

# Provider field -> stored field. A maturity absent from a session's response
# is stored as None, never 0 (spec Edge Cases — the curve must skip the point).
_MATURITY_FIELDS = {
    "month1": "m1", "month2": "m2", "month3": "m3", "month6": "m6",
    "year1": "y1", "year2": "y2", "year3": "y3", "year5": "y5",
    "year7": "y7", "year10": "y10", "year20": "y20", "year30": "y30",
}

# (dashboard key, display label, provider series name) — order matches the
# tile order contracts/macro-api.md pins for GET /market/economic-indicators.
# inflationRate/GDP/etc. deliberately overlap tools/macro.py's FRED series;
# see specs/017-fmp-migration-admin/data-model.md's amendment note (research D3).
INDICATOR_SERIES: list[tuple[str, str, str]] = [
    ("growth", "GDP", "GDP"),
    ("inflation", "Inflation rate", "inflationRate"),
    ("employment", "Unemployment rate", "unemploymentRate"),
    ("policy_rate", "Federal funds rate", "federalFunds"),
    ("consumer_sentiment", "Consumer sentiment", "consumerSentiment"),
    ("retail_sales", "Retail sales", "retailSales"),
]

CALENDAR_FORWARD_DAYS = 14
CALENDAR_BACK_DAYS = 7
_CALENDAR_IMPACT_LEVELS = {"High", "Medium"}

_PROVIDER_ERRORS = (FmpBudgetExceededError, requests.HTTPError, requests.RequestException)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Treasury rates ──────────────────────────────────────────────────────────

def _backfill_windows(
    total_days: int = BACKFILL_TOTAL_DAYS,
    window_days: int = BACKFILL_WINDOW_DAYS,
    today: date | None = None,
) -> list[tuple[date, date]]:
    """Non-overlapping [start, end] date pairs covering `total_days` back from
    `today`, each no wider than `window_days` — pure, no network, so backfill
    coverage is testable without a provider call."""
    today = today or _utcnow().date()
    start = today - timedelta(days=total_days)
    windows = []
    cursor = start
    while cursor < today:
        end = min(cursor + timedelta(days=window_days), today)
        windows.append((cursor, end))
        cursor = end + timedelta(days=1)
    return windows


def _map_treasury_row(raw: dict) -> dict | None:
    """None when the row has no parseable date or carries no maturity at all —
    both are dropped rather than stored as a half-empty session."""
    date_str = raw.get("date")
    if not date_str:
        return None
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    row: dict = {"date": date_str, "source": "fmp", "collected_at": _utcnow()}
    has_value = False
    for provider_key, stored_key in _MATURITY_FIELDS.items():
        value = raw.get(provider_key)
        row[stored_key] = float(value) if value is not None else None
        if value is not None:
            has_value = True
    return row if has_value else None


def _store_treasury_rows(db: Database, raw_rows: list[dict] | None) -> int:
    count = 0
    for raw in raw_rows or []:
        row = _map_treasury_row(raw)
        if row is None:
            continue
        db[TREASURY_RATES].update_one({"date": row["date"]}, {"$set": row}, upsert=True)
        count += 1
    return count


def _backfill_done(db: Database) -> bool:
    doc = db[DATASET_META].find_one({"dataset": BACKFILL_DATASET})
    return bool(doc and doc.get("last_run_status") == "success")


def _last_treasury_date(db: Database) -> str | None:
    doc = db[TREASURY_RATES].find_one({}, sort=[("date", -1)])
    return doc["date"] if doc else None


def pull_treasury_rates(db: Database) -> int:
    """One-time ~2-year backfill in <=90-day windows (FR-017a), guarded by a
    completion marker so it never repeats; thereafter a single incremental
    call per day from the last stored session forward (FR-017b) — narrow
    historical ranges are honored by the provider even though wide ones are
    truncated (research D2), so both paths use ranged requests."""
    if not _backfill_done(db):
        count = 0
        for start, end in _backfill_windows():
            rows = fmp_get(f"treasury-rates?from={start.isoformat()}&to={end.isoformat()}", db=db)
            count += _store_treasury_rows(db, rows)
        write_dataset_meta(BACKFILL_DATASET, "success", count, source="fmp", db=db)
        return count

    today = _utcnow().date()
    last_date = _last_treasury_date(db)
    from_date = date.fromisoformat(last_date) if last_date else today - timedelta(days=BACKFILL_TOTAL_DAYS)
    rows = fmp_get(f"treasury-rates?from={from_date.isoformat()}&to={today.isoformat()}", db=db)
    return _store_treasury_rows(db, rows)


# ── Economic calendar ───────────────────────────────────────────────────────

def _parse_calendar_dt(raw: str) -> datetime:
    """Provider timestamps are naive UTC (e.g. "2026-09-04 12:30:00")."""
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def pull_economic_calendar(db: Database) -> int:
    """Fetches a rolling window and filters to US + High/Medium impact at
    collect time (research D6) — the raw feed is ~90% low-impact and non-US
    noise. Upserts on (date, event); rows that have aged out of the window are
    pruned so the collection never grows without bound."""
    today = _utcnow().date()
    start = today - timedelta(days=CALENDAR_BACK_DAYS)
    end = today + timedelta(days=CALENDAR_FORWARD_DAYS)
    raw = fmp_get(f"economic-calendar?from={start.isoformat()}&to={end.isoformat()}", db=db)

    count = 0
    for r in raw or []:
        if r.get("country") != "US" or r.get("impact") not in _CALENDAR_IMPACT_LEVELS:
            continue
        if not r.get("date") or not r.get("event"):
            continue
        try:
            event_dt = _parse_calendar_dt(r["date"])
        except ValueError:
            continue
        doc = {
            "date": event_dt,
            "event": r["event"],
            "country": "US",
            "currency": r.get("currency"),
            "impact": r["impact"],
            "previous": r.get("previous"),
            "estimate": r.get("estimate"),
            "actual": r.get("actual"),
            "unit": r.get("unit"),
            "source": "fmp",
            "collected_at": _utcnow(),
        }
        db[ECONOMIC_CALENDAR_EVENTS].update_one(
            {"date": doc["date"], "event": doc["event"]}, {"$set": doc}, upsert=True
        )
        count += 1

    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)
    db[ECONOMIC_CALENDAR_EVENTS].delete_many(
        {"$or": [{"date": {"$lt": start_dt}}, {"date": {"$gt": end_dt}}]}
    )
    return count


# ── Economic indicators ─────────────────────────────────────────────────────

def pull_economic_indicators(db: Database) -> int:
    """One call per series — the endpoint takes a single `name` and ignores
    from/to (research D4), so depth can't be requested, only accumulated.
    Readings are upserted and never deleted (FR-024b): a series returning a
    single reading per call gains a usable prior value over successive runs.
    A failing series is skipped, not fatal — the other series still land."""
    count = 0
    for _key, _label, series in INDICATOR_SERIES:
        try:
            raw = fmp_get(f"economic-indicators?name={series}", db=db)
        except _PROVIDER_ERRORS:
            logger.warning("economic-indicators pull failed for series=%s", series, exc_info=True)
            continue
        for r in raw or []:
            date_str = r.get("date")
            value = r.get("value")
            if not date_str or value is None:
                continue
            reading_date = date_str[:10]
            db[ECONOMIC_INDICATORS].update_one(
                {"indicator": series, "date": reading_date},
                {"$set": {"indicator": series, "date": reading_date, "value": float(value),
                          "source": "fmp", "collected_at": _utcnow()}},
                upsert=True,
            )
            count += 1
    return count


# ── Market risk premium ─────────────────────────────────────────────────────

def pull_market_risk_premium(db: Database) -> int:
    """The provider returns ~190 countries with no date field at all (research
    D5) — only the US row is kept, replaced in place each run, keyed on
    `country` since that's the only stable identity available."""
    raw = fmp_get("market-risk-premium", db=db)
    us = next((r for r in (raw or []) if r.get("country") == "United States"), None)
    if us is None:
        return 0
    db[MARKET_RISK_PREMIUM].update_one(
        {"country": "United States"},
        {"$set": {
            "country": "United States",
            "total_equity_risk_premium": us.get("totalEquityRiskPremium"),
            "country_risk_premium": us.get("countryRiskPremium"),
            "source": "fmp",
            "collected_at": _utcnow(),
        }},
        upsert=True,
    )
    return 1


# ── Orchestrator ─────────────────────────────────────────────────────────────

def run_economics_pull(db: Database) -> int:
    """Runs all four sub-pulls, each isolated from the others' failures
    (FR-027 pushed down to the data layer). `dataset_meta.economics` reflects
    "success" only when every sub-pull succeeded this run — but a sub-pull
    that DID succeed has already written its fresher data regardless, so one
    provider outage degrades only the collection it touched, not the other
    three (constitution IV: fail soft, serve stale)."""
    total = 0
    any_failure = False
    for name, pull in (
        ("treasury_rates", pull_treasury_rates),
        ("economic_calendar", pull_economic_calendar),
        ("economic_indicators", pull_economic_indicators),
        ("market_risk_premium", pull_market_risk_premium),
    ):
        try:
            total += pull(db)
        except _PROVIDER_ERRORS:
            logger.warning("economics pull: %s failed", name, exc_info=True)
            any_failure = True

    status = "failed" if any_failure else "success"
    write_dataset_meta("economics", status, total, source="fmp", db=db)
    return total
