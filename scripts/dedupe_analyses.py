"""One-time cleanup: collapses pre-existing duplicate analysis records down to
one per ticker (the most recent by `timestamp`). Spec: specs/016-dedupe-analysis-feed.

Safe to run more than once — a second run finds nothing left to remove. Run
outside Docker, from the repo root:
    python scripts/dedupe_analyses.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-runner"))

from logging_config import get_logger  # noqa: E402
from tools.db import ANALYSES, ensure_indexes, get_db  # noqa: E402

logger = get_logger(__name__, component="scripts")


def dedupe(db) -> int:
    """Collapses each ticker's analysis docs to just the most recent.
    Returns the number of documents removed."""
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$ticker", "keep": {"$first": "$_id"}, "ids": {"$push": "$_id"}}},
    ]

    tickers_processed = 0
    removed = 0
    for group in db[ANALYSES].aggregate(pipeline):
        tickers_processed += 1
        stale_ids = [i for i in group["ids"] if i != group["keep"]]
        if stale_ids:
            result = db[ANALYSES].delete_many({"_id": {"$in": stale_ids}})
            removed += result.deleted_count

    ensure_indexes(db)
    return removed


if __name__ == "__main__":
    try:
        db = get_db()
        removed = dedupe(db)
        total_tickers = len(db[ANALYSES].distinct("ticker"))
        print(f"dedupe complete: {removed} duplicate record(s) removed, "
              f"{total_tickers} ticker(s) now have exactly one stored analysis")
    except Exception:
        logger.exception("dedupe_analyses failed")
        raise
