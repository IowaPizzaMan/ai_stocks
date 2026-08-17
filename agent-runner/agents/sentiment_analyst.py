"""SentimentAnalyst: news tone + earnings surprise track record.
Spec: specs/component-specs/agent-runner/agents/sentiment_analyst.md

Transcript endpoints are premium-tier (see tools/sentiment.py), so the agent
reads recent headlines and the EPS surprise history instead. Keyword counts
are computed deterministically; the LLM reads tone and evidence.
"""
import json

from llm import generate_json

BULLISH_KEYWORDS = ["accelerating", "record", "strong demand", "raised guidance", "confident",
                    "outperform", "inflection", "momentum", "beat", "upgrade", "strong"]
CAUTIOUS_KEYWORDS = ["headwind", "uncertainty", "cautious", "challenging", "monitoring",
                     "softness", "normalizing", "slowdown", "miss", "downgrade", "cut"]

SYSTEM = (
    "You listen carefully to what is being said about a company — and what isn't. You "
    "track language patterns: 'accelerating', 'strong demand' signal confidence; "
    "'headwinds', 'cautious', 'uncertain' signal caution. You weigh recency and whether "
    "earnings surprises back up the narrative."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "current_tone": {
            "type": "string",
            "enum": ["bullish", "cautiously_optimistic", "neutral", "cautious", "bearish"],
        },
        "tone_evidence": {"type": "array", "items": {"type": "string"}},
        "earnings_surprise_read": {"type": "string"},
        "narrative": {"type": "string"},
        "overall_sentiment_signal": {
            "type": "string",
            "enum": ["bullish", "mildly_bullish", "neutral", "mildly_bearish", "bearish"],
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["current_tone", "tone_evidence", "earnings_surprise_read", "narrative",
                 "overall_sentiment_signal", "confidence"],
}


def count_keywords(news: list[dict]) -> dict:
    """Deterministic keyword tally over headlines + summaries."""
    text = " ".join(
        f"{n.get('headline') or ''} {n.get('summary') or ''}" for n in news
    ).lower()
    bullish = {k: text.count(k) for k in BULLISH_KEYWORDS if text.count(k)}
    cautious = {k: text.count(k) for k in CAUTIOUS_KEYWORDS if text.count(k)}
    return {
        "bullish_keywords": {"terms": sorted(bullish), "count": sum(bullish.values())},
        "cautious_keywords": {"terms": sorted(cautious), "count": sum(cautious.values())},
    }


def run(ticker: str, context: dict, client=None) -> dict:
    """context: {'sentiment': tools/sentiment.get_earnings_sentiment() output,
    optionally 'news_timeline'/'news_trend' from tools/news.py so this read and
    the timeline chart on the Sentiment tab agree (spec 021 US6)}"""
    data = context["sentiment"]
    news = data.get("news", [])
    surprises = data.get("earnings_surprises", [])
    keywords = count_keywords(news)
    news_timeline = context.get("news_timeline") or []
    news_trend = context.get("news_trend")

    timeline_section = ""
    if news_timeline:
        timeline_section = f"""
## Dated news-language trend (deterministic, same data the UI charts)
trend: {news_trend}
per-date bullish/bearish term counts: {json.dumps(news_timeline, default=str)}
Your tone read should be consistent with this trend, or explain why it differs.
"""

    prompt = f"""Analyze sentiment for {ticker} from the last 30 days of news and the EPS
surprise history. (Earnings call transcripts aren't available on this data plan — work
from headlines and hard results; don't fabricate management quotes.)

## Recent headlines
{json.dumps(news, default=str)}

## EPS surprise history (newest first)
{json.dumps(surprises, default=str)}

## Deterministic keyword tally
{json.dumps(keywords)}
{timeline_section}
1. current_tone with 2-4 tone_evidence bullets citing specific headlines.
2. earnings_surprise_read: beats vs misses pattern and its direction.
3. narrative: 2-3 sentences; note when news volume is thin.
4. overall_sentiment_signal and confidence (thin/stale news = lower confidence)."""

    report = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
    return {
        **keywords,
        "news_count": len(news),
        "transcripts_available": bool(data.get("transcripts")),
        **report,
    }
