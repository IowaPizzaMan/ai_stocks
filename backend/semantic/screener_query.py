"""Shared question -> MongoDB aggregation pipeline generation against the
`screener` collection. Spec: specs/033-strategy-picks-filters; research.md R3.

Extracted from chat.py (031-semantic-layer-chat) so both the existing
free-form chat flow and the strategy-picks condition-translation flow
(semantic/condition_filter.py) call the exact same LLM-driven
question-to-query mechanism, rather than one being a hand-copied
reimplementation of the other (FR-004). Pure code motion — no behavior
change for the existing free-form flow (FR-009).
"""
import llm
from semantic.schema import NEWS_SCHEMA, SCREENER_SCHEMA

QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "collection": {"type": "string"},
        "pipeline": {"type": "array", "items": {"type": "object"}},
        "in_scope": {"type": "boolean"},
        # 036-news-semantic-search — required in practice only for
        # collection == "news_articles"; a missing / null value is treated as
        # {"mode": "recency"} (contracts/chat-news-retrieval.md §1). Value
        # constraints (query_text <= 400 chars, 0-4 candidate_tags, ticker in
        # the known universe) are enforced by coerce_news_search(), not the
        # schema.
        "news_search": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["recency", "semantic"]},
                "ticker": {"type": ["string", "null"]},
                "query_text": {"type": "string"},
                "candidate_tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["mode", "ticker", "query_text", "candidate_tags"],
        },
    },
    "required": ["collection", "pipeline", "in_scope"],
}

# contracts/chat-news-retrieval.md §1 field rules.
NEWS_QUERY_TEXT_MAX = 400
NEWS_CANDIDATE_TAGS_MAX = 4
NEWS_CANDIDATE_TAG_CHARS_MAX = 60


def coerce_news_search(raw, *, question: str, known_tickers: set[str] | None = None) -> dict:
    """Normalizes the model's `news_search` object to a safe, fully-populated
    shape (contracts/chat-news-retrieval.md §1 "On violation" column):

    - missing / not a dict            -> {"mode": "recency", ...}
    - mode not in {recency,semantic}  -> "recency"
    - ticker unknown / not a string   -> None (topic path)
    - query_text empty                -> the raw user question
    - candidate_tags over-long        -> trimmed to 60 chars, first 4 kept
    """
    known = known_tickers or set()
    data = raw if isinstance(raw, dict) else {}

    mode = data.get("mode")
    mode = mode if mode in ("recency", "semantic") else "recency"

    ticker = data.get("ticker")
    if isinstance(ticker, str):
        ticker = ticker.strip().upper()
        ticker = ticker if ticker in known else None
    else:
        ticker = None

    query_text = data.get("query_text")
    if not isinstance(query_text, str) or not query_text.strip():
        query_text = question
    query_text = query_text.strip()[:NEWS_QUERY_TEXT_MAX]

    raw_tags = data.get("candidate_tags")
    tags: list[str] = []
    if isinstance(raw_tags, list):
        for entry in raw_tags:
            if not isinstance(entry, str) or not entry.strip():
                continue
            tags.append(entry.strip()[:NEWS_CANDIDATE_TAG_CHARS_MAX])
            if len(tags) == NEWS_CANDIDATE_TAGS_MAX:
                break

    return {"mode": mode, "ticker": ticker, "query_text": query_text, "candidate_tags": tags}


def _field_line(f: dict) -> str:
    """One field's prompt line, appending its optional unit/enum/aggregation
    hints (data-model.md §3) when present — additive metadata only, the base
    name/type/description shape is unchanged from before 035."""
    bits = [f"  - {f['name']} ({f['type']}): {f['description']}"]
    if f.get("unit"):
        bits.append(f"[unit: {f['unit']}]")
    if f.get("enum"):
        bits.append(f"[allowed values: {', '.join(f['enum'])}]")
    if f.get("aggregation"):
        bits.append(f"[{f['aggregation']}]")
    return " ".join(bits)


def _schema_block(schema: dict) -> str:
    fields = "\n".join(_field_line(f) for f in schema["fields"])
    return f"Collection `{schema['collection']}`: {schema['description']}\n\nFields:\n{fields}"


def build_system_prompt() -> str:
    # 035-chat-and-news-upgrade US3 — multi-collection: the model picks which
    # of the two collections a question is actually about (research.md R2).
    # One LLM call, not a separate intent classifier in front of every
    # question — see plan.md's Summary for why.
    screener_block = _schema_block(SCREENER_SCHEMA)
    news_block = _schema_block(NEWS_SCHEMA)
    return (
        "You translate a user's question into a MongoDB aggregation "
        "pipeline against ONE of the following two collections — pick "
        "whichever the question is actually about.\n\n"
        f"{screener_block}\n\n{news_block}\n\n"
        'Reply with a JSON object: {"collection": "screener" or '
        '"news_articles", "pipeline": [...aggregation stages...], '
        '"in_scope": true|false}.\n'
        "Every pipeline stage is an object with exactly one key, and that key "
        'MUST start with a dollar sign — "$match", "$sort", "$limit", etc.\n\n'
        "If the question asks for a filtered list of individual stocks, use "
        '$match/$sort/$limit. Example for "stocks below a 20-day z-score of '
        '-1, sorted by weekly change":\n'
        '[{"$match": {"zscore_20d": {"$lt": -1}}}, '
        '{"$sort": {"weekly_change_pct": -1}}, {"$limit": 50}]\n\n'
        "If the question asks for an aggregate across multiple stocks — an "
        'average, a total, a count, or a breakdown "by" some category — use '
        "$group with an accumulator ($avg, $sum, $count) instead of "
        "returning a filtered list of individual stocks. A field marked "
        '[groupable] above is meant to be a $group _id; one marked [numeric] '
        'is meant to be averaged/summed. Example for "average weekly change '
        'percent by sector":\n'
        '[{"$group": {"_id": "$sector", '
        '"avg_weekly_change_pct": {"$avg": "$weekly_change_pct"}}}, '
        '{"$sort": {"avg_weekly_change_pct": -1}}]\n\n'
        "If the question asks about news for a specific ticker, target "
        '`news_articles` and match the tickers array. Example for "latest '
        'news on NVDA":\n'
        '[{"$match": {"tickers": "NVDA"}}, {"$sort": {"published_at": -1}}, '
        '{"$limit": 10}]\n\n'
        "If the question asks about news on a topic rather than a specific "
        'ticker, target `news_articles` and use $text as the FIRST stage. '
        'Example for "any recent news about tariffs":\n'
        '[{"$match": {"$text": {"$search": "tariffs"}}}, '
        '{"$sort": {"published_at": -1}}, {"$limit": 10}]\n\n'
        f"{_news_search_guidance()}"
        "Set in_scope to false (and pipeline to []) if the question cannot be "
        "answered using only the fields listed above — never invent a field "
        "or guess at data you don't have."
    )


def _news_search_guidance() -> str:
    """036-news-semantic-search — the `news_search` object + mode routing
    (contracts/chat-news-retrieval.md §1-2). Only meaningful when
    collection == "news_articles"; the model still emits a `pipeline` (kept for
    transparency and used as the keyword fallback), but for
    mode == "semantic" the engine ranks by meaning instead of running it."""
    return (
        "WHEN the collection is `news_articles`, ALSO return a `news_search` "
        "object choosing how the news should be retrieved:\n"
        '{"mode": "recency" | "semantic", "ticker": "NVDA" | null, '
        '"query_text": "<the question\'s intent, cleaned up>", '
        '"candidate_tags": ["<0-4 broad topic guesses>"]}\n'
        "- mode \"recency\": the question just wants the latest stories for a "
        'ticker or feed ("latest NVDA news", "any headlines on TSLA today"). '
        "Set `ticker` and leave `candidate_tags` empty.\n"
        "- mode \"semantic\": the question is about a TOPIC or a REASON, not "
        'just recency ("news about tariffs", "what\'s happening with rate '
        'cuts", "anything on consumer spending"). For a pure topic question '
        "set `ticker` to null. For a question that names a ticker AND asks "
        '"why" it moved or focuses on a topic ("why did NVDA drop today", '
        '"what\'s behind the TSLA move", "NVDA news about export bans") set '
        "`ticker` to that symbol — this is ticker-reason mode, NOT plain "
        "recency. Fill `query_text` with the underlying intent, and put 0-4 "
        "broad, reusable topic guesses in `candidate_tags` "
        '(e.g. ["monetary policy", "interest rates"] for a rate-cut question). '
        "Do NOT put company names or tickers in `candidate_tags`.\n"
        'Examples: "news about tariffs" -> {"mode": "semantic", "ticker": '
        'null, "query_text": "trade tariffs and import duties", '
        '"candidate_tags": ["tariffs", "trade policy"]}; '
        '"why did NVDA drop today" -> {"mode": "semantic", "ticker": "NVDA", '
        '"query_text": "why nvidia stock fell today", "candidate_tags": '
        '["semiconductors"]}; '
        '"latest Apple news" -> {"mode": "recency", "ticker": "AAPL", '
        '"query_text": "latest Apple news", "candidate_tags": []}.\n\n'
    )


def criteria_from_pipeline(pipeline: list[dict]) -> list[dict]:
    """Best-effort plain-language rendering of the pipeline's $match stages
    for FR-013. This is transparency, not a full query-plan explainer — a
    pipeline with no $match (or one built from $expr/computed fields) simply
    yields an empty criteria list, which is itself informative."""
    criteria = []
    for stage in pipeline:
        match = stage.get("$match")
        if not isinstance(match, dict):
            continue
        for field, cond in match.items():
            if field.startswith("$"):
                continue
            if isinstance(cond, dict):
                for op, value in cond.items():
                    criteria.append({"label": f"{field} {op} {value}",
                                      "field": field, "op": op, "value": value})
            else:
                criteria.append({"label": f"{field} = {cond}",
                                  "field": field, "op": "=", "value": cond})
    return criteria


def generate_pipeline(prompt_text: str, *, client=None) -> dict:
    """One Ollama call constrained to QUERY_SCHEMA. Returns
    {"collection": str, "pipeline": list[dict], "in_scope": bool}. May raise
    llm.LLMError."""
    return llm.generate_json(
        prompt=prompt_text,
        schema=QUERY_SCHEMA,
        system=build_system_prompt(),
        client=client,
        options={"temperature": 0},
    )
