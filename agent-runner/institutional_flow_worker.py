"""Market-wide institutional flow scan on its own daily timer (not per-ticker).
Spec: specs/component-specs/agent-runner/institutional_flow_worker.md

Called every tick from main.py's loop; actually scans once per UTC day after
`institutional_scan_hour_utc` (settings), or immediately when the API sets the
`manual_scan_requested` flag (POST /institutional/scan → "Scan Now" button).

Window notes:
- Dataroma moves are fetched since the last scan (the page is a daily diff).
- 13F changes use a fixed ~100-day lookback instead of the last-scan window:
  yfinance's "Date Reported" is the quarter end, so a 24h window would never
  match anything. Dedup below makes re-scanning the same rows idempotent —
  each quarterly refresh surfaces a row once.
- Deviation from the spec (same one as the earnings calendar, per user
  request): a scan does NOT auto-register or enqueue its tickers. Events are
  feed-only; tickers enter the system one at a time via the flow card's Queue
  button (POST /queue/{ticker}).
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from agents import institutional_flow_scanner
from settings import settings
from tools import institutional as institutional_tool
from tools import superinvestor as superinvestor_tool
from tools.db import INSTITUTIONAL_FLOW, INSTITUTIONAL_FLOW_META, get_db

logger = logging.getLogger(__name__)

FILING_LOOKBACK_DAYS = 100   # covers one 13F cycle (filings post ~45d after quarter end)
DATAROMA_DEDUP_DAYS = 7      # same fund/ticker/action within a week = same move re-scraped


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_meta(db, key: str):
    doc = db[INSTITUTIONAL_FLOW_META].find_one({"key": key})
    return doc.get("value") if doc else None


def _set_meta(db, key: str, value) -> None:
    db[INSTITUTIONAL_FLOW_META].replace_one({"key": key}, {"key": key, "value": value}, upsert=True)


def _claim_manual_request(db) -> bool:
    """Consume the manual-scan flag (claimed once, even if the scan then fails,
    so a broken scrape can't retry-loop every poll tick)."""
    doc = db[INSTITUTIONAL_FLOW_META].find_one_and_update(
        {"key": "manual_scan_requested", "value": True},
        {"$set": {"value": False}},
    )
    return doc is not None


def _scheduled_due(now: datetime, last_scan_at: datetime | None) -> bool:
    if now.hour < settings.institutional_scan_hour_utc:
        return False
    if last_scan_at is None:
        return True
    if last_scan_at.tzinfo is None:  # Mongo returns naive UTC datetimes
        last_scan_at = last_scan_at.replace(tzinfo=timezone.utc)
    return last_scan_at.date() < now.date()


def _fund_key(fund: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fund.lower())


def _same_fund(key_a: str, key_b: str) -> bool:
    """LLM extraction words fund names differently run to run ("Torray Fund"
    vs "Torray Funds", with/without the manager's name) — treat normalized
    containment either way as the same fund."""
    return bool(key_a) and bool(key_b) and (key_a in key_b or key_b in key_a)


def _is_duplicate(db, event: dict, batch: list[dict]) -> bool:
    if event["source"] == "13F":
        # deterministic source: same holder row re-emitted while it stays
        # inside the lookback window
        key = {"source": "13F", "fund": event["fund"], "ticker": event["ticker"],
               "action": event["action"], "filed_at": event["filed_at"]}
        return (db[INSTITUTIONAL_FLOW].find_one(key) is not None
                or any(e["source"] == "13F" and e["fund"] == event["fund"]
                       and e["ticker"] == event["ticker"] and e["action"] == event["action"]
                       and e["filed_at"] == event["filed_at"] for e in batch))

    # dataroma: filed_at is scan time and the extraction is non-deterministic,
    # so match any recent event for the ticker with a fuzzy fund-name match,
    # regardless of action (buy/new_position wobble between runs too)
    cutoff = event["filed_at"] - timedelta(days=DATAROMA_DEDUP_DAYS)
    for doc in db[INSTITUTIONAL_FLOW].find(
            {"source": "dataroma", "ticker": event["ticker"], "filed_at": {"$gte": cutoff}},
            {"fund": 1, "fund_key": 1}):
        if _same_fund(event["fund_key"], doc.get("fund_key") or _fund_key(doc.get("fund", ""))):
            return True
    return any(e["source"] == "dataroma" and e["ticker"] == event["ticker"]
               and _same_fund(event["fund_key"], e["fund_key"]) for e in batch)


def run_scan(db=None, client=None, now: datetime | None = None) -> int:
    """Full sweep: fetch both sources → build events → dedup → insert.
    Returns the number of new events written."""
    db = db if db is not None else get_db()
    now = now or _utcnow()
    since = _get_meta(db, "last_scan_at") or now - timedelta(hours=24)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    dataroma_moves = superinvestor_tool.get_recent_superinvestor_moves(since, client=client)
    filing_changes = institutional_tool.get_recent_13f_changes(
        now - timedelta(days=FILING_LOOKBACK_DAYS), db=db)

    raw_events = institutional_flow_scanner.run(
        dataroma_moves=dataroma_moves, filing_changes=filing_changes, client=client, now=now)
    events: list[dict] = []
    for e in raw_events:
        e["fund_key"] = _fund_key(e["fund"])
        if not _is_duplicate(db, e, events):
            events.append(e)

    if events:
        for e in events:
            e["scanned_at"] = now
        db[INSTITUTIONAL_FLOW].insert_many(events)

    _set_meta(db, "last_scan_at", now)
    logger.info("institutional flow scan wrote %s new events", len(events))
    return len(events)


def run_daily_scan_if_due(now: datetime, db=None, scan=None) -> int | None:
    """Called every main-loop tick. Returns the event count when a scan ran,
    None otherwise. A failed scan leaves last_scan_at unchanged so the next
    scheduled attempt re-covers the same window."""
    db = db if db is not None else get_db()
    scan = scan if scan is not None else run_scan

    manual = _claim_manual_request(db)
    if not manual and not _scheduled_due(now, _get_meta(db, "last_scan_at")):
        return None

    logger.info("starting institutional flow scan (%s)", "manual" if manual else "scheduled")
    try:
        return scan(db=db, now=now)
    except Exception:
        logger.exception("institutional flow scan failed")
        return None
