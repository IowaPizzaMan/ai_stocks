"""The semantic layer description fed to the model for chat query generation.
Spec: specs/031-semantic-layer-chat; data-model.md; contracts/chat-api.md.

`SCREENER_SCHEMA["fields"]` names are the mirrored contract table shared with
agent-runner/tools/screener.py's `compute_signals()` output and asserted
equal in both services' tests (backend/tests/test_screener_contract.py,
agent-runner/tests/test_screener.py) — constitution Principle VI. A field
present in the collection but missing here is invisible to the model; a
field described but not present produces queries that silently match
nothing. Both failure modes are what that mirrored assertion exists to catch.

specs/035-chat-and-news-upgrade US1 (FR-011, research.md R4) adds optional
`unit`/`enum`/`aggregation` keys to fields below — additive only, never a
field rename/add/remove, so the mirrored name-set assertion above is
unaffected. `aggregation: "numeric"` marks a field worth $avg/$sum-ing;
`aggregation: "groupable"` marks one worth $group-ing by (a category or
flag, not an identifier like `ticker`/`name`). `enum` closes off a field's
value set so the model doesn't invent a value that matches nothing.
"""

SCREENER_SCHEMA: dict = {
    "collection": "screener",
    "description": (
        "One document per stock symbol, holding pre-computed screening "
        "signals. Covers both individually tracked stocks and the broader "
        "market universe used for market-wide comparisons (see is_tracked). "
        "Any field may be null when there isn't enough history to compute "
        "it — null means unknown, never \"does not match\"."
    ),
    "fields": [
        {"name": "ticker", "type": "string",
         "description": "Stock ticker symbol, e.g. \"AAPL\"."},
        {"name": "name", "type": "string",
         "description": "Company name. Null if the company profile hasn't been fetched."},
        {"name": "sector", "type": "string", "aggregation": "groupable",
         "description": "GICS-style sector, e.g. \"Technology\"."},
        {"name": "industry", "type": "string", "aggregation": "groupable",
         "description": "Industry within the sector."},
        {"name": "market_cap", "type": "number", "unit": "USD", "aggregation": "numeric",
         "description": "Market capitalization in USD."},
        {"name": "is_tracked", "type": "boolean", "aggregation": "groupable",
         "description": (
             "True if the user actively tracks this stock (full analysis "
             "available); false if it only appears here as part of the "
             "broader market universe used for breadth calculations."
         )},
        {"name": "last_close", "type": "number", "unit": "USD", "aggregation": "numeric",
         "description": "Most recent daily closing price."},
        {"name": "last_bar_date", "type": "string",
         "description": "Date (YYYY-MM-DD) of the most recent price bar."},
        {"name": "range_pct_20d", "type": "number", "unit": "fraction", "aggregation": "numeric",
         "description": (
             "Position of the last close within its 20-day high/low range, "
             "0.0 = at the 20-day low, 1.0 = at the 20-day high. A low value "
             "means the stock is near the bottom of its recent daily range."
         )},
        {"name": "zscore_20d", "type": "number", "unit": "standard deviations", "aggregation": "numeric",
         "description": (
             "Last close vs. its 20-day mean, in standard deviations. "
             "Negative means below average, positive means above average."
         )},
        {"name": "weekly_change_pct", "type": "number", "unit": "percent", "aggregation": "numeric",
         "description": "Percent price change over the past ~5 trading days (one week). Positive = up on the week."},
        {"name": "monthly_change_pct", "type": "number", "unit": "percent", "aggregation": "numeric",
         "description": "Percent price change over the past ~21 trading days (one month)."},
        {"name": "weekly_trend", "type": "string", "enum": ["up", "down", "flat"], "aggregation": "groupable",
         "description": "One of \"up\", \"down\", \"flat\" — the sign of weekly_change_pct."},
        {"name": "revenue_growth_yoy", "type": "number", "unit": "fraction", "aggregation": "numeric",
         "description": "Year-over-year revenue growth, fractional (0.12 = +12%)."},
        {"name": "net_income_growth_yoy", "type": "number", "unit": "fraction", "aggregation": "numeric",
         "description": "Year-over-year net income growth, fractional."},
        {"name": "net_profit_margin", "type": "number", "unit": "fraction", "aggregation": "numeric",
         "description": "Most recent annual net profit margin, fractional."},
        {"name": "margin_trend", "type": "string",
         "enum": ["improving", "flat", "deteriorating"], "aggregation": "groupable",
         "description": "One of \"improving\", \"flat\", \"deteriorating\" — net margin vs. the prior annual period. Null if fewer than 2 annual periods are available."},
        {"name": "financials_trend", "type": "string",
         "enum": ["improving", "flat", "deteriorating"], "aggregation": "groupable",
         "description": (
             "One of \"improving\", \"flat\", \"deteriorating\" — a composite "
             "of revenue growth, net income growth, and margin trend. "
             "\"improving\" means the fundamentals are getting better; "
             "\"deteriorating\" means they are getting worse. Null if fewer "
             "than 2 annual periods are available."
         )},
        {"name": "free_cash_flow", "type": "number", "unit": "USD", "aggregation": "numeric",
         "description": "Most recent annual free cash flow, in USD."},
        {"name": "total_debt", "type": "number", "unit": "USD", "aggregation": "numeric",
         "description": "Most recent annual total debt, in USD."},
        {"name": "fcf_exceeds_debt", "type": "boolean", "aggregation": "groupable",
         "description": "True when free_cash_flow > total_debt."},
        {"name": "signals_as_of", "type": "date",
         "description": "When this document's signals were last computed."},
        {"name": "price_data_through", "type": "string",
         "description": "Date (YYYY-MM-DD) the underlying price history is current through."},
        {"name": "financials_as_of", "type": "string",
         "description": "Fiscal period-end date (YYYY-MM-DD) of the most recent annual financials used."},
        {"name": "insufficient_history", "type": "boolean", "aggregation": "groupable",
         "description": "True when there are fewer than 25 daily price bars — every price-derived field above is then null."},
        {"name": "liked_status", "type": "string",
         "enum": ["liked", "disliked"], "aggregation": "groupable",
         "description": (
             "The user's personal like/dislike marking for this ticker, set "
             "from the stock page's like/dislike control. One of \"liked\", "
             "\"disliked\", or null if never marked."
         )},
    ],
}

# 035-chat-and-news-upgrade US3 — the second schema `screener_query.py`'s
# system prompt describes, so the model can choose which collection a
# question is actually about. `fields` names are the mirrored contract table
# shared with agent-runner's tools/news_pull.py normalizer output, asserted
# equal in both services' tests (backend/tests/test_news_contract.py,
# agent-runner/tests/test_news_contract.py) — constitution Principle VI
# (amended v1.1.0), same discipline as SCREENER_SCHEMA above.
NEWS_SCHEMA: dict = {
    "collection": "news_articles",
    "description": (
        "One document per news story from any of three sources: general "
        "market news (no associated ticker), FMP editorial articles, and "
        "company-specific stock news. To find news about a specific ticker, "
        "match on the `tickers` array — it is indexed and exact. To find "
        "news about a topic (not a specific ticker), use a $text search on "
        "the first pipeline stage, e.g. "
        '{"$match": {"$text": {"$search": "tariffs"}}}} — $text only works '
        "as the very first stage of the pipeline."
    ),
    "fields": [
        {"name": "url", "type": "string",
         "description": "The story's source URL — also its unique identity."},
        {"name": "source_type", "type": "string",
         "enum": ["general", "stock", "fmp_article"], "aggregation": "groupable",
         "description": (
             "Which of the three feeds this story came from: \"general\" "
             "(market-wide news, no ticker), \"stock\" (company-specific "
             "news), or \"fmp_article\" (FMP editorial analysis)."
         )},
        {"name": "title", "type": "string",
         "description": "The story's headline."},
        {"name": "published_at", "type": "date", "aggregation": "numeric",
         "description": "When the story was published. Use this for recency sorting and date-range questions."},
        {"name": "published_date", "type": "string",
         "description": "Date (YYYY-MM-DD) the story was published — for day-granularity filtering without date arithmetic."},
        {"name": "publisher", "type": "string", "aggregation": "groupable",
         "description": "The story's publisher/source, e.g. \"CNBC\"."},
        {"name": "site", "type": "string", "aggregation": "groupable",
         "description": "The publisher's domain, e.g. \"cnbc.com\". Null when the feed doesn't supply one."},
        {"name": "author", "type": "string",
         "description": "The story's byline author. Only present on fmp_article stories."},
        {"name": "body_html", "type": "string",
         "description": "Raw HTML body, when the source supplied formatting. Null for general/stock stories."},
        {"name": "body_text", "type": "string",
         "description": "Plain-text body/blurb — search and read this field, not body_html."},
        {"name": "image_url", "type": "string",
         "description": "The story's thumbnail image URL, if any."},
        {"name": "tickers", "type": "array", "aggregation": "groupable",
         "description": (
             "Tickers this story is about. Empty for general market news. "
             "Prefer matching this field over $text for ticker-scoped questions."
         )},
        {"name": "ingested_at", "type": "date", "aggregation": "numeric",
         "description": "When this system stored the story — not when it was published; use published_at for that."},
        # 036-news-semantic-search — the one enrichment field that is
        # model-legible (data-model.md §3). The five internal fields
        # (embedding, embedding_model, embedding_dim, embedded_at,
        # tags_generated_at) are deliberately NOT here — see
        # contracts/news-collection-v2.md §2 and test_news_contract.py.
        {"name": "tags", "type": "array", "aggregation": "groupable",
         "description": (
             "Free-form topic labels assigned to this story at ingestion "
             "(e.g. \"monetary policy\", \"semiconductors\", \"oil prices\"). "
             "The chat engine matches a topic question to these automatically "
             "and pre-filters on them before ranking — you normally do NOT "
             "need to $match on tags yourself. Use them only for an explicit "
             "\"stories tagged X\" style request."
         )},
    ],
}
