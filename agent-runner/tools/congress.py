"""congress_trades_pull — Senate/House trading disclosures.
Spec: specs/028-dashboard-tweaks-batch US4.
Contract: specs/028-dashboard-tweaks-batch/contracts/congress-api.md

Reuses the `congress_trades` collection schema spec 017 already pinned
(specs/017-fmp-migration-admin/data-model.md) rather than inventing a
parallel shape (Principle VI, R7). The legacy `congressional_trades`
collection (Quiver-era, retired) is confirmed dead — referenced only in
specs/data_fetcher.py, a spec-era file, not live code.

Field mapping confirmed against a user-supplied live response (research.md
R7); exact JSON key casing is the one part still assumed (candidate keys
below), which is why the normalizer reads tolerantly rather than assuming
one exact shape.
"""
import hashlib
import re
from datetime import date, datetime, timedelta, timezone

from logging_config import get_logger
from tools.db import CONGRESS_TRADES
from tools.fmp_client import fmp_get

logger = get_logger(__name__)

HIGH_DOLLAR_THRESHOLD = 100_001
DEFAULT_WINDOW_DAYS = 90

_SALE_PREFIX = "sale"


def is_purchase(transaction_type: str | None) -> bool:
    """"Purchase"/"Sale"/"Sale (Full)"/"Sale (Partial)" — capitalised words,
    not buy/sell (R7). Only an exact "purchase" match counts; any sale
    variant, including the partial-sale forms these filings commonly use,
    must never be counted as a buy."""
    if not transaction_type:
        return False
    return transaction_type.strip().lower() == "purchase"


def parse_amount_bounds(amount_range: str | None) -> tuple[int, int] | None:
    """Extracts (lower, upper) from a disclosed bracket string. Tolerates
    '$', thousands separators, hyphen or en-dash separators, and an
    open-ended "Over $X" form (returned as (X, X), which still passes a
    >= threshold test correctly). Returns None for anything unparseable —
    never raises, never estimates a midpoint (FR-016a)."""
    if not amount_range:
        return None
    numbers = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", amount_range)]
    if not numbers:
        return None
    if len(numbers) == 1:
        return (numbers[0], numbers[0])
    return (numbers[0], numbers[1])


def _trade_id(ticker, person_id, transaction_date, transaction_type, amount_range, owner) -> str:
    """Composite hash — the provider supplies no per-trade id (R7). Must
    include transaction_type and owner: a member filing a same-day Purchase
    and Sale of one ticker, or holding a trade Joint vs Self, would otherwise
    collide and silently overwrite one another."""
    parts = "|".join(str(p) for p in
                      (ticker, person_id, transaction_date, transaction_type, amount_range, owner))
    return hashlib.sha256(parts.encode()).hexdigest()[:24]


def _first(raw: dict, *keys):
    for k in keys:
        v = raw.get(k)
        if v not in (None, ""):
            return v
    return None


def _normalize_row(raw: dict, chamber: str) -> dict | None:
    ticker = _first(raw, "symbol", "ticker")
    first_name = _first(raw, "firstName", "first_name")
    last_name = _first(raw, "lastName", "last_name")
    office = _first(raw, "office")
    politician = f"{first_name} {last_name}".strip() if (first_name or last_name) else None
    politician = politician or office

    if not ticker and not politician:
        return None

    person_id = _first(raw, "senateId", "senate_id", "bioguideId")
    transaction_type = _first(raw, "type", "transactionType")
    amount_range = _first(raw, "amount", "amountRange")
    transaction_date = _first(raw, "transactionDate", "transaction_date")
    disclosure_date = _first(raw, "disclosureDate", "disclosure_date")
    owner = _first(raw, "owner") or None

    return {
        "trade_id": _trade_id(ticker, person_id, transaction_date, transaction_type, amount_range, owner),
        "chamber": chamber,
        "person_id": person_id,
        "politician": politician,
        "district": _first(raw, "district"),
        "owner": owner,
        "ticker": ticker,
        "asset_description": _first(raw, "assetDescription", "asset_description"),
        "asset_type": _first(raw, "assetType", "asset_type"),
        "transaction_type": transaction_type,
        "amount_range": amount_range,
        "transaction_date": transaction_date,
        "disclosure_date": disclosure_date,
        "link": _first(raw, "link"),
        "source": "fmp",
        "collected_at": datetime.now(timezone.utc),
    }


def _fetch_chamber(path: str, chamber: str, db) -> list[dict]:
    raw_rows = fmp_get(path, db=db)
    rows = []
    for raw in raw_rows:
        row = _normalize_row(raw, chamber)
        if row is None:
            logger.warning("congress_trades_pull: skipping unrecognizable %s row", chamber)
            continue
        rows.append(row)
    return rows


def run_congress_trades_pull(db) -> int:
    """work_queue admin-job handler for job_type="congress_trades_pull".
    Each chamber is fetched independently so one failing does not lose the
    other's rows (Principle IV); raises only if both fail, so the job is
    correctly marked failed rather than silently reporting success."""
    senate_rows: list[dict] = []
    house_rows: list[dict] = []
    senate_error = house_error = None

    try:
        senate_rows = _fetch_chamber("senate-latest", "senate", db)
    except Exception as exc:  # noqa: BLE001 - isolate this chamber's failure
        senate_error = exc
        logger.warning("congress_trades_pull: senate fetch failed: %s", exc)

    try:
        house_rows = _fetch_chamber("house-latest", "house", db)
    except Exception as exc:  # noqa: BLE001 - isolate this chamber's failure
        house_error = exc
        logger.warning("congress_trades_pull: house fetch failed: %s", exc)

    if senate_error is not None and house_error is not None:
        raise senate_error

    for row in senate_rows + house_rows:
        db[CONGRESS_TRADES].update_one(
            {"trade_id": row["trade_id"]}, {"$set": row}, upsert=True,
        )
    return len(senate_rows) + len(house_rows)


def rank_most_bought(rows: list[dict], now: datetime, days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
    """Tickers ranked by number of buy disclosures within the window,
    windowed on disclosure_date (not transaction_date — disclosures are
    routinely filed weeks-to-months late, so a transaction-date window would
    hide newly-disclosed old trades, exactly the ones worth surfacing)."""
    cutoff = (now - timedelta(days=days)).date()
    counts: dict[str, int] = {}
    for row in rows:
        if not row.get("ticker") or not is_purchase(row.get("transaction_type")):
            continue
        try:
            d = date.fromisoformat(str(row["disclosure_date"])[:10])
        except (ValueError, KeyError):
            continue
        if d < cutoff:
            continue
        counts[row["ticker"]] = counts.get(row["ticker"], 0) + 1

    return [
        {"ticker": t, "buy_count": c}
        for t, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def high_dollar(rows: list[dict], now: datetime, days: int = DEFAULT_WINDOW_DAYS,
                 threshold: int = HIGH_DOLLAR_THRESHOLD) -> list[dict]:
    """Disclosures in the window whose bracket's upper bound reaches the
    threshold. Never computes a midpoint or point value (FR-016a)."""
    cutoff = (now - timedelta(days=days)).date()
    flagged = []
    for row in rows:
        try:
            d = date.fromisoformat(str(row["disclosure_date"])[:10])
        except (ValueError, KeyError):
            continue
        if d < cutoff:
            continue
        bounds = parse_amount_bounds(row.get("amount_range"))
        if bounds is None or bounds[1] < threshold:
            continue
        flagged.append(row)

    return sorted(flagged, key=lambda r: r["disclosure_date"], reverse=True)
