"""FMP company profile + peers + employee-count history, cached in Mongo.
Spec: specs/029-company-profile-tweaks/contracts/company-profile-api.md

Three datasets, one document per ticker in `company_info` (reserved since
017, never written to until now). The profile refreshes on every pull;
peers and employee counts sit behind a 90-day cache window matching
tools/financials.py's CACHE_DAYS, since they only change when the company
files (spec clarification). Each dataset carries its own `*_fetched_at` /
`*_outcome` marker so a 402/budget-degraded dataset is retried on the next
pull without freezing for the whole window or sliding the other two
datasets' windows — the same lesson spec 018 learned about financials
(the BSX bug).

sector/industry/name/logo_url are denormalized onto ticker_index here too
(research R3) — that collection already has a `sector` field
(registry.register_ticker) that nothing has ever populated, which is why
GET /sectors has always been empty (KNOWN_ISSUES.md's first open bug).
"""
from datetime import datetime, timedelta, timezone

import requests
from pymongo.database import Database

from logging_config import get_logger
from tools.db import COMPANY_INFO, TICKER_INDEX, get_db
from tools.fmp_client import FmpBudgetExceededError, fmp_get

logger = get_logger(__name__)

CACHE_DAYS = 90


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_profile(raw: dict) -> dict:
    """FMP's `profile` row -> our snake_case shape. `range` is kept as the
    provider's own "low-high" string (data-model.md) — parsing it here would
    lose the provider's formatting for the rare symbol that returns something
    non-numeric; the backend splits it for display."""
    return {
        "name": raw.get("companyName"),
        "exchange": raw.get("exchange"),
        "exchange_full": raw.get("exchangeFullName"),
        "sector": raw.get("sector") or None,
        "industry": raw.get("industry") or None,
        "country": raw.get("country"),
        "currency": raw.get("currency"),
        "website": raw.get("website"),
        "ceo": raw.get("ceo"),
        "full_time_employees": raw.get("fullTimeEmployees"),
        "ipo_date": raw.get("ipoDate"),
        "description": raw.get("description"),
        "image": raw.get("image"),
        "default_image": bool(raw.get("defaultImage")),
        "cik": raw.get("cik"),
        "isin": raw.get("isin"),
        "cusip": raw.get("cusip"),
        "phone": raw.get("phone"),
        "address": raw.get("address"),
        "city": raw.get("city"),
        "state": raw.get("state"),
        "zip": raw.get("zip"),
        "market_cap": raw.get("marketCap"),
        "beta": raw.get("beta"),
        "last_dividend": raw.get("lastDividend"),
        "range": raw.get("range"),
        "average_volume": raw.get("averageVolume"),
        "price": raw.get("price"),
        "change": raw.get("change"),
        "change_percentage": raw.get("changePercentage"),
        "volume": raw.get("volume"),
        "is_etf": bool(raw.get("isEtf")),
        "is_fund": bool(raw.get("isFund")),
        "is_adr": bool(raw.get("isAdr")),
        "is_actively_trading": bool(raw.get("isActivelyTrading")),
    }


def _normalize_peer(raw: dict) -> dict:
    return {
        "symbol": raw.get("symbol"),
        "name": raw.get("companyName") or raw.get("name"),
        "price": raw.get("price"),
        "market_cap": raw.get("mktCap") or raw.get("marketCap"),
    }


def _normalize_employee_record(raw: dict) -> dict:
    return {
        "period_of_report": raw.get("periodOfReport"),
        "filing_date": raw.get("filingDate"),
        "form_type": raw.get("formType"),
        "employee_count": raw.get("employeeCount"),
        "source": raw.get("source"),
    }


def get_profile(ticker: str, db: Database | None = None) -> tuple[dict | None, str]:
    """Returns (profile, outcome). outcome is `confirmed` (FMP answered,
    payload may be empty/None) or `unavailable` (402/403/budget — degrade,
    never raise)."""
    db = db if db is not None else get_db()
    try:
        raw = fmp_get(f"profile?symbol={ticker}", db=db)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status not in (402, 403):
            raise
        logger.info("FMP %s for %s/profile — not covered on this plan, skipping", status, ticker)
        return None, "unavailable"
    except FmpBudgetExceededError:
        logger.warning("FMP daily soft cap exceeded — skipping profile for %s", ticker)
        return None, "unavailable"

    rows = raw if isinstance(raw, list) else [raw] if raw else []
    if not rows:
        return None, "confirmed"
    return _normalize_profile(rows[0]), "confirmed"


def get_peers(ticker: str, db: Database | None = None) -> tuple[list[dict], str]:
    db = db if db is not None else get_db()
    try:
        raw = fmp_get(f"stock-peers?symbol={ticker}", db=db)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status not in (402, 403):
            raise
        logger.info("FMP %s for %s/stock-peers — not covered on this plan, skipping", status, ticker)
        return [], "unavailable"
    except FmpBudgetExceededError:
        logger.warning("FMP daily soft cap exceeded — skipping peers for %s", ticker)
        return [], "unavailable"

    rows = raw if isinstance(raw, list) else []
    return [_normalize_peer(r) for r in rows], "confirmed"


def get_employee_counts(ticker: str, db: Database | None = None) -> tuple[list[dict], str]:
    db = db if db is not None else get_db()
    try:
        raw = fmp_get(f"historical-employee-count?symbol={ticker}", db=db)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status not in (402, 403):
            raise
        logger.info(
            "FMP %s for %s/historical-employee-count — not covered on this plan, skipping",
            status, ticker,
        )
        return [], "unavailable"
    except FmpBudgetExceededError:
        logger.warning("FMP daily soft cap exceeded — skipping employee counts for %s", ticker)
        return [], "unavailable"

    rows = raw if isinstance(raw, list) else []
    records = [_normalize_employee_record(r) for r in rows]
    records.sort(key=lambda r: r.get("period_of_report") or "")
    return records, "confirmed"


def _is_stale(fetched_at: datetime | None) -> bool:
    if fetched_at is None:
        return True
    if fetched_at.tzinfo is None:  # mongomock/pymongo return naive UTC
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return fetched_at < _utcnow() - timedelta(days=CACHE_DAYS)


def _sync_ticker_index(ticker: str, profile: dict | None, db: Database) -> None:
    """Denormalize sector/industry/name/logo_url onto ticker_index (R3) — the
    single query every filter/rollup reads, so this is the one write that
    makes the Sectors page, the sector filter, and the new industry filter
    all agree by construction."""
    if profile is None:
        return
    logo_url = None if profile.get("default_image") or not profile.get("image") else profile["image"]
    update: dict = {"$set": {}}
    if profile.get("sector"):
        update["$set"]["sector"] = profile["sector"]
    if profile.get("industry"):
        update["$set"]["industry"] = profile["industry"]
    if profile.get("name"):
        update["$set"]["name"] = profile["name"]
    update["$set"]["logo_url"] = logo_url
    if update["$set"]:
        db[TICKER_INDEX].update_one({"ticker": ticker}, update)


def refresh_company_info(ticker: str, mode: str = "delta", db: Database | None = None) -> dict:
    """Orchestrates all three fetches, respecting each dataset's own cache
    window. mode="full" bypasses every window (FR-008b). Never raises — a
    profile fetch failure must not sink the pull it's attached to (FR-009)."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()
    now = _utcnow()

    existing = db[COMPANY_INFO].find_one({"ticker": ticker}) or {}
    full = mode == "full"

    set_fields: dict = {"ticker": ticker}

    # profile: always refetched (FR-008)
    profile, profile_outcome = get_profile(ticker, db=db)
    if profile is not None or profile_outcome == "confirmed":
        set_fields["profile"] = profile
        set_fields["profile_fetched_at"] = now
        set_fields["profile_outcome"] = profile_outcome
    else:
        # degraded — keep whatever was stored before, don't overwrite with None
        set_fields["profile"] = existing.get("profile")
        set_fields["profile_fetched_at"] = existing.get("profile_fetched_at")
        set_fields["profile_outcome"] = profile_outcome

    # peers: 90-day window, retried immediately if previously unavailable
    peers_needs_refresh = (
        full
        or existing.get("peers_outcome") != "confirmed"
        or _is_stale(existing.get("peers_fetched_at"))
    )
    if peers_needs_refresh:
        peers, peers_outcome = get_peers(ticker, db=db)
        if peers_outcome == "confirmed":
            set_fields["peers"] = peers
            set_fields["peers_fetched_at"] = now
        else:
            set_fields["peers"] = existing.get("peers", [])
            set_fields["peers_fetched_at"] = existing.get("peers_fetched_at")
        set_fields["peers_outcome"] = peers_outcome
    else:
        set_fields["peers"] = existing.get("peers", [])
        set_fields["peers_fetched_at"] = existing.get("peers_fetched_at")
        set_fields["peers_outcome"] = existing.get("peers_outcome", "confirmed")

    # employee_counts: 90-day window, same shape as peers
    employees_needs_refresh = (
        full
        or existing.get("employee_counts_outcome") != "confirmed"
        or _is_stale(existing.get("employee_counts_fetched_at"))
    )
    if employees_needs_refresh:
        records, employees_outcome = get_employee_counts(ticker, db=db)
        if employees_outcome == "confirmed":
            set_fields["employee_counts"] = records
            set_fields["employee_counts_fetched_at"] = now
        else:
            set_fields["employee_counts"] = existing.get("employee_counts", [])
            set_fields["employee_counts_fetched_at"] = existing.get("employee_counts_fetched_at")
        set_fields["employee_counts_outcome"] = employees_outcome
    else:
        set_fields["employee_counts"] = existing.get("employee_counts", [])
        set_fields["employee_counts_fetched_at"] = existing.get("employee_counts_fetched_at")
        set_fields["employee_counts_outcome"] = existing.get("employee_counts_outcome", "confirmed")

    db[COMPANY_INFO].replace_one({"ticker": ticker}, set_fields, upsert=True)
    _sync_ticker_index(ticker, set_fields.get("profile"), db)
    return set_fields
