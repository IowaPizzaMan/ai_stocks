"""Cross-stock AI summary — gather, condense, rank/cap, and persist.
Spec: specs/027-stocks-news-tab-ai-summary
Contract: specs/027-stocks-news-tab-ai-summary/contracts/portfolio-digest-api.md

`analyses` already holds exactly one document per ticker (unique index,
upsert-on-write), so "every tracked stock's most recent analysis" needs no
extra dedupe — just a read. Condensing trims each document to what a
synthesis actually needs (mirrors portfolio_strategist.py's own "assessments,
not raw series" trim), and the 25-stock cap keeps the prompt inside Ollama's
num_ctx budget (research.md R5) by keeping the highest-conviction stocks
first (clarified 2026-08-21).
"""
from datetime import datetime, timezone

from agents import portfolio_digest as portfolio_digest_agent
from logging_config import get_logger
from tools.db import ANALYSES, PORTFOLIO_DIGEST_CACHE

logger = get_logger(__name__)

MAX_STOCKS = 25
CONVICTION_RANK = {"high": 3, "medium": 2, "low": 1}

_PROJECTION = {
    "_id": 0, "ticker": 1, "signal": 1, "conviction": 1, "summary": 1,
    "key_trends": 1, "flags": 1, "timestamp": 1, "sub_reports.news.stance": 1,
}


def _sort_key(doc: dict) -> tuple[int, float]:
    rank = CONVICTION_RANK.get(doc.get("conviction"), 0)
    ts = doc.get("timestamp")
    ts_value = ts.timestamp() if isinstance(ts, datetime) else 0.0
    return (-rank, -ts_value)


def _condense(doc: dict) -> dict:
    stance = ((doc.get("sub_reports") or {}).get("news") or {}).get("stance")
    return {
        "ticker": doc.get("ticker"),
        "signal": doc.get("signal"),
        "conviction": doc.get("conviction"),
        "summary": doc.get("summary"),
        "key_trends": doc.get("key_trends") or [],
        "flags": doc.get("flags") or [],
        "news_stance": stance,
    }


def gather_and_rank(db, cap: int = MAX_STOCKS) -> tuple[list[dict], int, bool]:
    """Returns (condensed stocks capped and sorted by conviction-then-recency,
    total tracked count, whether the cap actually trimmed anything)."""
    docs = list(db[ANALYSES].find({}, _PROJECTION))
    total = len(docs)
    docs.sort(key=_sort_key)
    capped = total > cap
    selected = docs[:cap]
    return [_condense(d) for d in selected], total, capped


def run_portfolio_digest(db, client=None) -> int:
    """work_queue admin-job handler for job_type="portfolio_digest"
    (registered in tools/admin_jobs.py). Returns stock_count for
    dataset_meta-style record counts, though this job type is deliberately
    not tracked in dataset_meta (research.md R6)."""
    condensed, total, capped = gather_and_rank(db)
    now = datetime.now(timezone.utc)

    if not condensed:
        db[PORTFOLIO_DIGEST_CACHE].update_one(
            {},
            {"$set": {
                "generated_at": now, "overview": None, "highlights": [],
                "stock_count": 0, "total_tracked_count": total, "capped": capped,
            }},
            upsert=True,
        )
        return 0

    try:
        result = portfolio_digest_agent.run(condensed, client=client)
    except Exception as exc:
        logger.exception("portfolio digest synthesis failed")
        db[PORTFOLIO_DIGEST_CACHE].update_one(
            {}, {"$set": {"last_error": str(exc), "last_error_at": now}}, upsert=True,
        )
        raise

    db[PORTFOLIO_DIGEST_CACHE].update_one(
        {},
        {"$set": {
            "generated_at": now,
            "overview": result.get("overview"),
            "highlights": result.get("highlights", []),
            "stock_count": len(condensed),
            "total_tracked_count": total,
            "capped": capped,
        }},
        upsert=True,
    )
    return len(condensed)
