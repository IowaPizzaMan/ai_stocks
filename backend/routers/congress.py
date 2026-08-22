"""GET/POST /congress/* — Congress trading disclosures.
Spec: specs/028-dashboard-tweaks-batch US4.
Contract: specs/028-dashboard-tweaks-batch/contracts/congress-api.md

Read-only over congress_trades, written by the agent-runner's
congress_trades_pull admin job (agent-runner/tools/congress.py). This router
never calls a provider itself; POST /refresh only enqueues that job.

Supersedes specs/017-fmp-migration-admin's provisional (never implemented,
no consumer) GET /market/congress-trades sketch — see the supersession note
in that spec's contracts/market-data-api.md (R10). The congress_trades
schema itself is unchanged from 017's pin (Principle VI).

The summary math (rank_most_bought / high_dollar / parse_amount_bounds) is
hand-synced with agent-runner/tools/congress.py's pure functions, same
duplication precedent as price_store.py (Principle V/VI — the services
share no package).
"""
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from db import CONGRESS_TRADES, WORK_QUEUE
from deps import db_dependency

router = APIRouter(prefix="/congress", tags=["congress"])

DEFAULT_WINDOW_DAYS = 90
HIGH_DOLLAR_THRESHOLD = 100_001
_BIOGUIDE_ID_RE = re.compile(r"^[A-Za-z]\d{6}$")


# --- hand-synced pure functions (agent-runner/tools/congress.py) --------------

def is_purchase(transaction_type: str | None) -> bool:
    if not transaction_type:
        return False
    return transaction_type.strip().lower() == "purchase"


def parse_amount_bounds(amount_range: str | None) -> tuple[int, int] | None:
    if not amount_range:
        return None
    numbers = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", amount_range)]
    if not numbers:
        return None
    if len(numbers) == 1:
        return (numbers[0], numbers[0])
    return (numbers[0], numbers[1])


def rank_most_bought(rows: list[dict], now: datetime, days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
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


# --- endpoints -----------------------------------------------------------------

@router.get("/trades")
def get_trades(
    ticker: str | None = None,
    politician: str | None = None,
    chamber: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db=Depends(db_dependency),
):
    filter: dict = {}
    if ticker:
        filter["ticker"] = {"$regex": re.escape(ticker), "$options": "i"}
    if politician:
        # A value shaped like a bioguide id (e.g. "B001236") matches person_id
        # exactly — stable per member, so it resolves a lawmaker filed under
        # varying name spellings. Anything else falls back to substring on
        # the display name (R7).
        if _BIOGUIDE_ID_RE.match(politician):
            filter["person_id"] = politician.upper()
        else:
            filter["politician"] = {"$regex": re.escape(politician), "$options": "i"}
    if chamber:
        filter["chamber"] = chamber

    total = db[CONGRESS_TRADES].count_documents(filter)
    items = list(
        db[CONGRESS_TRADES].find(filter, {"_id": 0})
        .sort("disclosure_date", -1)
        .limit(limit)
    )
    as_of = max((i["collected_at"] for i in items), default=None)
    return {"items": items, "total": total, "as_of": as_of.isoformat() if as_of else None}


@router.get("/summary")
def get_summary(db=Depends(db_dependency)):
    """Pure arithmetic over stored rows — no LLM (Principle III)."""
    now = datetime.now(timezone.utc)
    rows = list(db[CONGRESS_TRADES].find({}, {"_id": 0}))
    flagged = high_dollar(rows, now=now)
    as_of = max((r["collected_at"] for r in rows), default=None)
    return {
        "window_days": DEFAULT_WINDOW_DAYS,
        "most_bought": rank_most_bought(rows, now=now),
        "high_dollar": flagged,
        "high_dollar_threshold": f"${HIGH_DOLLAR_THRESHOLD:,}",
        "as_of": as_of.isoformat() if as_of else None,
    }


@router.post("/refresh")
def refresh_congress_trades(db=Depends(db_dependency)):
    existing = db[WORK_QUEUE].find_one(
        {"job_type": "congress_trades_pull", "status": {"$in": ["pending", "running"]}}
    )
    if existing:
        return {"status": "already_queued", "job_id": str(existing["_id"])}

    now = datetime.now(timezone.utc)
    result = db[WORK_QUEUE].insert_one({
        "job_type": "congress_trades_pull",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    })
    return {"status": "enqueued", "job_id": str(result.inserted_id)}
