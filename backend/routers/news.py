"""News API — the mixed general/stock/FMP-article stream.
Spec: specs/035-chat-and-news-upgrade; contracts/news-api.md.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from db import NEWS_ARTICLES, WORK_QUEUE
from deps import db_dependency

router = APIRouter(prefix="/news", tags=["news"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _serialize(doc: dict) -> dict:
    published_at = doc.get("published_at")
    return {
        "url": doc["url"],
        "source_type": doc["source_type"],
        "title": doc["title"],
        "published_at": published_at.isoformat() if published_at else None,
        "published_date": doc.get("published_date"),
        "publisher": doc.get("publisher"),
        "site": doc.get("site"),
        "author": doc.get("author"),
        "body_html": doc.get("body_html"),
        "body_text": doc.get("body_text"),
        "image_url": doc.get("image_url"),
        "tickers": doc.get("tickers") or [],
    }


@router.get("")
def get_news(
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    source_type: str | None = None,
    ticker: str | None = None,
    db=Depends(db_dependency),
):
    """The mixed, recency-ordered stream (FR-005). Always returns 200 — an
    empty collection or an unset filter is a normal state, not an error
    (mirrors /market/news's reasoning)."""
    limit = max(1, min(limit, MAX_LIMIT))
    query: dict = {}
    if source_type:
        query["source_type"] = source_type
    if ticker:
        query["tickers"] = ticker.upper()

    total = db[NEWS_ARTICLES].count_documents(query)
    cursor = (
        db[NEWS_ARTICLES]
        .find(query, {"_id": 0})
        .sort("published_at", -1)
        .skip(max(offset, 0))
        .limit(limit)
    )
    articles = [_serialize(doc) for doc in cursor]

    latest = db[NEWS_ARTICLES].find_one({}, sort=[("ingested_at", -1)], projection={"ingested_at": 1})
    as_of = latest["ingested_at"].isoformat() if latest and latest.get("ingested_at") else None

    return {"articles": articles, "total": total, "as_of": as_of}


@router.post("/refresh")
def refresh_news(db=Depends(db_dependency)):
    """Enqueues market_news_pull — mirrors market.py's
    refresh_most_actives enqueue-or-dedupe shape exactly."""
    existing = db[WORK_QUEUE].find_one(
        {"job_type": "market_news_pull", "status": {"$in": ["pending", "running"]}}
    )
    if existing:
        return {"status": "already_queued", "job_id": str(existing["_id"])}

    now = datetime.now(timezone.utc)
    result = db[WORK_QUEUE].insert_one({
        "job_type": "market_news_pull",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    })
    return {"status": "enqueued", "job_id": str(result.inserted_id)}
