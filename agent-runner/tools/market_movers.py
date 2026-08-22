"""market_movers_pull — most-actives stocks (specs/028-dashboard-tweaks-batch US6).
Contract: specs/028-dashboard-tweaks-batch/contracts/market-movers-api.md

Registered in 017's job registry for all three categories (gainers/losers/
actives), but this batch implements only `actives` — the one FR-022 needs.
`category` is already part of 017's pinned schema, so the other two remain
valid values with no writer yet rather than requiring a schema change later
(R9).

The `most-actives` endpoint returns no volume field, so ordering cannot come
from that. Because `market_movers` is keyed on (date, category, ticker) and
written by upsert, Mongo does not preserve insertion order on read — so the
provider's own array position is stamped as `rank` and is what the read
endpoint sorts on.

No try/except here: a provider failure propagates naturally — nothing is
written until the fetch has already succeeded, so prior rows survive
untouched, and the caller (queue_worker._run_admin_job) marks the job failed
rather than lying about success.
"""
from datetime import date, datetime, timezone

from pymongo.database import Database

from tools.db import MARKET_MOVERS
from tools.fmp_client import fmp_get

CATEGORY = "actives"


def _normalize_row(raw: dict, rank: int, today: str, now: datetime) -> dict | None:
    ticker = raw.get("symbol")
    if not ticker:
        return None
    return {
        "date": today,
        "category": CATEGORY,
        "ticker": ticker,
        "company": raw.get("name"),
        "price": raw.get("price"),
        "change": raw.get("change"),
        # Already a percent (e.g. 3.35196 == +3.35%) — never multiplied by 100.
        "change_pct": raw.get("changesPercentage"),
        "exchange": raw.get("exchange"),
        "rank": rank,
        # No volume field in this response — explicitly None, never defaulted
        # to 0 (which would look like real data rather than "unknown").
        "volume": None,
        "source": "fmp",
        "collected_at": now,
    }


def run_market_movers_pull(db: Database) -> int:
    raw_rows = fmp_get("most-actives", db=db)
    today = date.today().isoformat()
    now = datetime.now(timezone.utc)

    rows = [
        row for i, raw in enumerate(raw_rows)
        if (row := _normalize_row(raw, i, today, now)) is not None
    ]

    for row in rows:
        db[MARKET_MOVERS].update_one(
            {"date": row["date"], "category": row["category"], "ticker": row["ticker"]},
            {"$set": row},
            upsert=True,
        )
    return len(rows)
