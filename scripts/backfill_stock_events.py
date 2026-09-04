"""One-time back-fill: seeds one "added" stock_event per already-tracked
ticker, dated from its ticker_index.first_seen_at (not the run time).
Spec: specs/037-stocks-conviction-and-activity; FR-021a; contracts/stock-events-api.md
tests #17-20; clarification Q7 ("added" only — "updated" history is not
reconstructible and is not back-filled).

Idempotent: skips any ticker that already has an "added" event, so re-running
after a partial failure (or after the live registration paths have already
started writing their own "added" events) never duplicates.

Run outside Docker, from the repo root:
    python scripts/backfill_stock_events.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-runner"))

from logging_config import get_logger  # noqa: E402
from tools.db import STOCK_EVENTS, TICKER_INDEX, ensure_indexes, get_db  # noqa: E402

logger = get_logger(__name__, component="scripts")


def backfill(db=None) -> int:
    """Returns the number of "added" events inserted (0 on a fully-idempotent
    re-run)."""
    db = db if db is not None else get_db()
    ensure_indexes(db)

    already = {
        row["ticker"] for row in db[STOCK_EVENTS].find(
            {"event_type": "added"}, {"_id": 0, "ticker": 1},
        )
    }

    inserted = 0
    for row in db[TICKER_INDEX].find({}, {"_id": 0, "ticker": 1, "first_seen_at": 1}):
        ticker = row["ticker"]
        if ticker in already:
            continue
        db[STOCK_EVENTS].insert_one({
            "ticker": ticker,
            "event_type": "added",
            "occurred_at": row.get("first_seen_at"),
            "changed": False,
            "changes": None,
            "reason": None,
            "source": "backfill",
        })
        inserted += 1

    return inserted


if __name__ == "__main__":
    try:
        count = backfill()
        print(f"back-filled {count} \"added\" event(s)")
    except Exception:
        logger.exception("stock_events back-fill failed")
        sys.exit("back-fill FAILED — see logs/scripts/scripts.log")
