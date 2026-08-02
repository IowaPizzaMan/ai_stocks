"""Sentiment inputs: company news + earnings surprises via Finnhub.
Spec: specs/component-specs/agent-runner/tools/sentiment.md

Sourcing (verified 2026-08-02): Finnhub's transcript endpoints are 403
premium-tier on this key. The SentimentAnalyst therefore reads recent company
news headlines plus the EPS surprise history — the free forward-looking
signals — and the transcript path stays dormant until a premium key exists
(`transcripts` is always [] with a note, so the agent prompt can say why).
"""
from datetime import date, timedelta

from tools.finnhub_client import finnhub_get

NEWS_DAYS = 30
MAX_HEADLINES = 25
SUMMARY_CHARS = 220


def get_earnings_sentiment(ticker: str, num_quarters: int = 8) -> dict:
    ticker = ticker.upper()
    to_date = date.today()
    from_date = to_date - timedelta(days=NEWS_DAYS)

    raw_news = finnhub_get("company-news", symbol=ticker,
                           **{"from": from_date.isoformat(), "to": to_date.isoformat()})
    news = []
    for item in raw_news[:MAX_HEADLINES]:
        news.append({
            "date": date.fromtimestamp(item["datetime"]).isoformat() if item.get("datetime") else None,
            "headline": item.get("headline"),
            "summary": (item.get("summary") or "")[:SUMMARY_CHARS],
            "source": item.get("source"),
        })

    surprises = finnhub_get("stock/earnings", symbol=ticker) or []

    return {
        "news": news,
        "earnings_surprises": surprises[:num_quarters],
        "transcripts": [],
        "transcripts_note": "earnings call transcripts require a premium Finnhub key — not available",
    }
