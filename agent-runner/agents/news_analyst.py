"""NewsAnalyst: per-article summaries and an overall stance on the coverage.
Spec: specs/021-stock-page-redesign (US5, US8 — FR-018, FR-024)

The bullish/bearish counting, timeline, and trend label are computed
deterministically in tools/news.py; this agent only writes prose — short
summaries for the newest articles and a stance that must cite what it read
(constitution Principle III).
"""
import json

from llm import generate_json
from logging_config import get_logger

logger = get_logger(__name__)

# Bounded so a mega-cap's news volume can't stretch a pull: the local model
# writes one summary per article, and older items stay listed with their
# excerpt instead (tools/news.py keeps the full set).
MAX_SUMMARIZED = 15
PROMPT_EXCERPT_CHARS = 600

SYSTEM = (
    "You read financial news the way an experienced analyst skims a wire: quickly "
    "separating what actually changes the investment case from noise, recycled "
    "headlines, and promotional filler. You never invent details that aren't in the "
    "article text, and you say when coverage is thin or one-sided."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "summaries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "summary": {"type": "string"},
                },
                "required": ["index", "summary"],
            },
        },
        "stance": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["bullish", "neutral", "bearish"]},
                "reasoning": {"type": "string"},
            },
            "required": ["direction", "reasoning"],
        },
    },
    "required": ["summaries", "stance"],
}


def run(ticker: str, context: dict, client=None) -> dict:
    """context: {'news': tools/news.get_stock_news() output}

    Returns the news sub-report: the same articles with `ai_summary` filled in
    for the newest MAX_SUMMARIZED, plus the stance. Deterministic fields
    (timeline, trend, counts) pass through untouched.
    """
    news = context["news"] or {}
    articles = news.get("articles", [])

    base = {
        "articles": articles,
        "timeline": news.get("timeline", []),
        "trend": news.get("trend", "mixed"),
        "news_count": news.get("news_count", len(articles)),
        "days_covered": news.get("days_covered", 0),
        "window_days": news.get("window_days", 0),
        "as_of": news.get("as_of"),
        "stance": None,
    }
    if not articles:
        return base

    to_summarize = articles[:MAX_SUMMARIZED]
    payload = [
        {
            "index": i,
            "date": a["date"],
            "source": a["source"],
            "headline": a["headline"],
            "text": a["text_excerpt"][:PROMPT_EXCERPT_CHARS],
            "bullish_terms": a["bullish_count"],
            "bearish_terms": a["bearish_count"],
        }
        for i, a in enumerate(to_summarize)
    ]

    prompt = f"""Review recent news coverage for {ticker}.

## Articles (newest first)
{json.dumps(payload, default=str)}

## Deterministic tone tally across all {base["news_count"]} articles from the last \
{base["days_covered"]} days with coverage
trend: {base["trend"]}
timeline (date, bullish terms, bearish terms): {json.dumps(base["timeline"], default=str)}

1. summaries: for EACH article above, a 1-3 sentence summary keyed by its `index`.
   Say what happened and why it matters to the stock. Do not repeat the headline
   verbatim, and do not add facts that aren't in the text.
2. stance: overall direction (bullish/neutral/bearish) with reasoning that cites at
   least one specific headline by name. Weigh substance over volume — one earnings
   miss outweighs five recycled opinion pieces. If coverage is thin or mostly
   promotional, say so and lean neutral."""

    report = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)

    # Map summaries back by index; anything the model skipped keeps ai_summary None
    # rather than silently shifting summaries onto the wrong article.
    by_index = {}
    for item in report.get("summaries", []):
        try:
            by_index[int(item["index"])] = item["summary"]
        except (KeyError, TypeError, ValueError):
            logger.warning("%s: malformed news summary entry: %r", ticker, item)

    merged = []
    for i, article in enumerate(articles):
        merged.append({**article, "ai_summary": by_index.get(i)} if i < MAX_SUMMARIZED else article)

    return {**base, "articles": merged, "stance": report.get("stance")}
