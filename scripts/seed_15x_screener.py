"""15x scale dry-run: seeds a synthetic `screener` collection at ~15x today's
tracked-universe size and reports the numbers that matter for SC-004.
Spec: specs/031-semantic-layer-chat; research.md R5; quickstart.md step 8.

Deliberately does NOT touch the real `stockai` database — it seeds a
separate database (default `stockai_scale_test`) so this dry run can never
corrupt real screening data. Run outside Docker, from the repo root:

    python scripts/seed_15x_screener.py            # seed + report, leaves the test DB
    python scripts/seed_15x_screener.py --cleanup   # also drops the test DB afterward
"""
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pymongo import ASCENDING, MongoClient  # noqa: E402

from settings import settings  # noqa: E402

TEST_DB_NAME = "stockai_scale_test"
TARGET_DOC_COUNT = 8340  # ~15x today's 556-document price_history universe (research.md R5)

SECTORS = ["Technology", "Healthcare", "Financials", "Energy", "Industrials",
           "Consumer Discretionary", "Consumer Staples", "Utilities"]
TRENDS = ["improving", "flat", "deteriorating", None]


def _synthetic_doc(i: int, now: datetime) -> dict:
    """Realistic-enough field distributions — not all-identical values, so
    query selectivity/index usage is representative rather than trivial."""
    rng = random.Random(i)
    insufficient = rng.random() < 0.05  # a few newly-added tickers, as in reality
    doc = {
        "ticker": f"SYN{i:05d}",
        "name": f"Synthetic Co {i}",
        "sector": rng.choice(SECTORS),
        "industry": "Synthetic Industry",
        "market_cap": rng.uniform(1e8, 3e12),
        "is_tracked": i < 975,  # ~15x today's 65 tracked tickers
        "signals_as_of": now,
        "price_data_through": "2026-08-21",
        "financials_as_of": "2025-12-31",
        "insufficient_history": insufficient,
    }
    if insufficient:
        doc.update({k: None for k in (
            "last_close", "last_bar_date", "range_pct_20d", "zscore_20d",
            "weekly_change_pct", "monthly_change_pct", "weekly_trend",
        )})
    else:
        last_close = rng.uniform(5, 800)
        doc.update({
            "last_close": last_close,
            "last_bar_date": "2026-08-21",
            "range_pct_20d": rng.uniform(0, 1),
            "zscore_20d": rng.uniform(-3, 3),
            "weekly_change_pct": rng.uniform(-10, 10),
            "monthly_change_pct": rng.uniform(-20, 20),
            "weekly_trend": rng.choice(["up", "down", "flat"]),
        })
    financials_trend = rng.choice(TRENDS)
    fcf = rng.uniform(-1e9, 5e10)
    debt = rng.uniform(0, 3e10)
    doc.update({
        "revenue_growth_yoy": rng.uniform(-0.3, 0.5),
        "net_income_growth_yoy": rng.uniform(-0.5, 0.8),
        "net_profit_margin": rng.uniform(-0.2, 0.4),
        "margin_trend": financials_trend,
        "financials_trend": financials_trend,
        "free_cash_flow": fcf,
        "total_debt": debt,
        "fcf_exceeds_debt": fcf > debt,
    })
    return doc


def seed(db, count: int = TARGET_DOC_COUNT) -> float:
    db["screener"].drop()
    now = datetime.now(timezone.utc)
    t0 = time.time()
    batch = []
    for i in range(count):
        batch.append(_synthetic_doc(i, now))
        if len(batch) >= 1000:
            db["screener"].insert_many(batch)
            batch = []
    if batch:
        db["screener"].insert_many(batch)
    # Only screener's own indexes — deliberately not the full backend
    # ensure_indexes(), which would touch ~14 unrelated collection names and
    # auto-create them as an empty-collection side effect in this throwaway
    # database (MongoDB creates a collection the first time create_index is
    # called against it).
    db["screener"].create_index([("ticker", ASCENDING)], unique=True)
    db["screener"].create_index([("range_pct_20d", ASCENDING)])
    db["screener"].create_index([("zscore_20d", ASCENDING)])
    db["screener"].create_index([("weekly_change_pct", ASCENDING)])
    db["screener"].create_index([("financials_trend", ASCENDING)])
    db["screener"].create_index([("fcf_exceeds_debt", ASCENDING)])
    db["screener"].create_index([("sector", ASCENDING)])
    db["screener"].create_index([("is_tracked", ASCENDING)])
    return time.time() - t0


def report(db) -> None:
    stats = db.command("collstats", "screener")
    print(f"screener document count: {db['screener'].count_documents({})}")
    print(f"screener data size:      {stats['size'] / 1_048_576:.2f} MB (uncompressed)")
    print(f"screener storage size:   {stats['storageSize'] / 1_048_576:.2f} MB (on disk)")
    print(f"screener index size:     {stats.get('totalIndexSize', 0) / 1_048_576:.2f} MB")

    # The query that matters: does the flagship-style filter stay fast at 15x?
    pipeline = [
        {"$match": {"zscore_20d": {"$lt": 0}, "weekly_trend": "up",
                    "financials_trend": "improving", "fcf_exceeds_debt": True}},
        {"$limit": 50},
    ]
    t0 = time.time()
    matches = list(db["screener"].aggregate(pipeline, maxTimeMS=5000))
    dt = time.time() - t0
    print(f"flagship-style query: {len(matches)} matches in {dt * 1000:.1f}ms")


if __name__ == "__main__":
    client = MongoClient(settings.mongo_uri)
    db = client[TEST_DB_NAME]

    print(f"Seeding {TARGET_DOC_COUNT} synthetic documents into {TEST_DB_NAME!r}.screener ...")
    elapsed = seed(db)
    print(f"seed time: {elapsed:.1f}s")
    report(db)

    if "--cleanup" in sys.argv:
        client.drop_database(TEST_DB_NAME)
        print(f"dropped {TEST_DB_NAME!r}")
    else:
        print(f"left {TEST_DB_NAME!r} in place — re-run with --cleanup to remove it")
