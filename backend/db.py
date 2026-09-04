"""MongoDB connection + collection accessors. Spec: specs/component-specs/backend/db.md"""
from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient
from pymongo.database import Database
from pymongo.errors import OperationFailure

from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

# Collection names — keep in sync with agent-runner/tools/db.py
ANALYSES = "analyses"
WORK_QUEUE = "work_queue"
WATCHLIST = "watchlist"
TICKER_INDEX = "ticker_index"
FINANCIALS_CACHE = "financials_cache"
# 0 live documents as of 2026-08-23, but do NOT treat as dead like
# FUND_HOLDINGS/STOCK_NEWS/MARKET_NEWS above were: this one is reserved for
# specs/007-earnings-transcripts (planned, not yet built), has an index
# bootstrapped below, is cleaned up on ticker deletion (routers/stocks.py),
# and that cleanup is asserted by test_routers.py — research.md R7.
TRANSCRIPTS_CACHE = "transcripts_cache"
MACRO_CACHE = "macro_cache"
MACRO_ANALYSIS_CACHE = "macro_analysis_cache"
INSTITUTIONAL_CACHE = "institutional_cache"
EARNINGS_SCANS = "earnings_scans"
EARNINGS_CACHE = "earnings_cache"
INSTITUTIONAL_FLOW = "institutional_flow"
INSTITUTIONAL_FLOW_META = "institutional_flow_meta"
BREADTH_CACHE = "breadth_cache"
BREADTH_UNIVERSE = "breadth_universe"
BREADTH_DIVERGENCES = "breadth_divergences"
BREADTH_META = "breadth_meta"
MARKET_FLOW_EVENTS = "market_flow_events"

# 017-fmp-migration-admin — keep in sync with agent-runner/tools/db.py.
# FUND_HOLDINGS/STOCK_NEWS/MARKET_NEWS (bare, distinct from *_CACHE below)
# were removed 2026-08-23 (specs/031-semantic-layer-chat, research.md R7) —
# no collection was ever created for them; they were dead constants only.
# FMP_ENTITLEMENTS below has 0 live documents for the same reason
# TRANSCRIPTS_CACHE does above — it's actively written
# (tools/fmp_client.py:191), just not yet exercised in this environment.
FMP_ENTITLEMENTS = "fmp_entitlements"
DATASET_META = "dataset_meta"
MARKET_MOVERS = "market_movers"
ECONOMIC_CALENDAR_EVENTS = "economic_calendar_events"
TREASURY_RATES = "treasury_rates"
MARKET_RISK_PREMIUM = "market_risk_premium"
ECONOMIC_INDICATORS = "economic_indicators"
CONGRESS_TRADES = "congress_trades"
COMPANY_INFO = "company_info"

# 021-stock-page-redesign — per-ticker pull-time caches, keep in sync with agent-runner/tools/db.py
STOCK_NEWS_CACHE = "stock_news_cache"
BENEFICIAL_OWNERSHIP_CACHE = "beneficial_ownership_cache"

# 022-market-news-feed — keep in sync with agent-runner/tools/db.py
MARKET_NEWS_CACHE = "market_news_cache"
FMP_USAGE = "fmp_usage"

# 024-delta-data-pulls — keep in sync with agent-runner/tools/db.py.
# price_history is a maintained store, not a cache: one doc per ticker holding the
# full daily series, extended incrementally. It deliberately has NO TTL — expiry
# would destroy the baseline every delta pull depends on. Retired price_cache.
PRICE_HISTORY = "price_history"
INSIDER_CACHE = "insider_cache"

# 026-macro-market-dashboard — agent-runner's economics_worker scheduling
# marker; backend never reads it, kept in sync per constitution VI convention.
ECONOMICS_META = "economics_meta"

# 031-semantic-layer-chat — flat, pre-computed, one-doc-per-ticker screening
# collection. Every queryable field is top-level by design (data-model.md):
# it's the only shape a locally-generated chat query can reliably target.
# agent-runner is the sole writer; backend only reads it. Keep in sync with
# agent-runner/tools/db.py per constitution Principle VI.
SCREENER = "screener"

# 032-weekly-strategy-picks — one-doc-per-ticker precomputed The Strat / Gap
# Analysis signals (direction, entry price, strength). Deliberately a
# separate collection from SCREENER, not new fields on it — see the matching
# comment in agent-runner/tools/db.py for why. agent-runner is the sole
# writer; backend only reads it here, plus BREADTH_CACHE above, to apply the
# Market Flow filter at read time (backend/semantic/market_flow_filter.py).
# Keep in sync with agent-runner/tools/db.py per constitution Principle VI.
STRATEGY_SIGNALS = "strategy_signals"

# 035-chat-and-news-upgrade — one document per news story from any of three
# FMP feeds (general market, FMP editorial articles, stock-specific).
# agent-runner is the sole writer (tools/news_pull.py); backend reads it both
# directly (routers/news.py) and via chat-generated aggregation pipelines
# (semantic/schema.py's NEWS_SCHEMA). Keep in sync with agent-runner/tools/db.py
# per constitution Principle VI (amended v1.1.0 — see contracts/news-collection.md).
NEWS_ARTICLES = "news_articles"

# 035-chat-and-news-upgrade US5 — one document per saved chat conversation,
# messages embedded. Backend-only: agent-runner never touches this
# collection, so no cross-service mirroring is required (unlike NEWS_ARTICLES
# above).
CHAT_CONVERSATIONS = "chat_conversations"

# 036-news-semantic-search — the in-use tag registry: one doc per distinct
# normalized topic tag, carrying its own embedding + usage count
# (data-model.md §2). agent-runner is the sole writer
# (tools/news_enrich.upsert_tag_registry); backend only reads it, directly
# with a fixed projection from semantic/news_rank.py — it is deliberately NOT
# in query_guard.READABLE_COLLECTIONS. Keep in sync with
# agent-runner/tools/db.py per constitution Principle VI
# (contracts/news-collection-v2.md §3).
NEWS_TAGS = "news_tags"

# 037-stocks-conviction-and-activity — append-only log backing both the
# Stocks-page activity feed (last 100, paged, routers/events.py) and each
# stock's per-ticker change-history trail. Two writers in agent-runner
# (register_ticker for "added", queue_worker.py for "updated") plus a
# mirrored "added" writer here in registry.py — the two services share no
# Python package. NOT admitted to query_guard.READABLE_COLLECTIONS (research.md
# R9) — server-internal only. Keep in sync with agent-runner/tools/db.py per
# constitution Principle VI.
STOCK_EVENTS = "stock_events"


@lru_cache(maxsize=1)
def get_db() -> Database:
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]


def ensure_indexes(db: Database) -> None:
    """Idempotent index bootstrap — called once at API startup."""
    db[ANALYSES].create_index([("ticker", ASCENDING), ("timestamp", DESCENDING)])
    db[ANALYSES].create_index([("timestamp", DESCENDING)])
    try:
        db[ANALYSES].create_index([("ticker", ASCENDING)], unique=True)
    except OperationFailure:
        logger.warning(
            "unique ticker index on analyses blocked by existing duplicates — "
            "run scripts/dedupe_analyses.py"
        )
    # 037-stocks-conviction-and-activity — backs GET /analysis/feed's
    # (conviction_rank desc, ticker asc) sort; a total order given the unique
    # ticker index above (contracts/feed-ordering.md).
    db[ANALYSES].create_index([("conviction_rank", DESCENDING), ("ticker", ASCENDING)])
    db[WORK_QUEUE].create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    db[WORK_QUEUE].create_index([("job_type", ASCENDING), ("created_at", DESCENDING)])
    db[TICKER_INDEX].create_index([("ticker", ASCENDING)], unique=True)
    db[TICKER_INDEX].create_index([("status", ASCENDING)])
    db[INSTITUTIONAL_FLOW].create_index([("filed_at", DESCENDING)])
    db[INSTITUTIONAL_FLOW].create_index([("ticker", ASCENDING), ("filed_at", DESCENDING)])
    db[BREADTH_CACHE].create_index([("exchange", ASCENDING), ("date", DESCENDING)])
    db[MARKET_FLOW_EVENTS].create_index([("created_at", DESCENDING)])
    # TTL caches (seconds): macro 24h; financials use quarterly re-fetch logic instead of TTL
    db[MACRO_CACHE].create_index("fetched_at", expireAfterSeconds=24 * 3600)
    # Market news is a single row keyed by source. Deliberately NO TTL index: the
    # 60-minute window is compared in code so the stale copy survives expiry and
    # can still be served when a refresh fails (specs/022 data-model.md §2).
    db[MARKET_NEWS_CACHE].create_index([("key", ASCENDING)], unique=True)
    # 026-macro-market-dashboard — written by agent-runner's economics_pull job;
    # backend only reads these, but declares the same indexes per constitution VI.
    db[TREASURY_RATES].create_index([("date", ASCENDING)], unique=True)
    db[ECONOMIC_CALENDAR_EVENTS].create_index([("date", ASCENDING), ("event", ASCENDING)], unique=True)
    db[ECONOMIC_CALENDAR_EVENTS].create_index([("date", DESCENDING)])
    db[ECONOMIC_INDICATORS].create_index([("indicator", ASCENDING), ("date", ASCENDING)], unique=True)
    db[ECONOMIC_INDICATORS].create_index([("indicator", ASCENDING), ("date", DESCENDING)])
    db[MARKET_RISK_PREMIUM].create_index([("country", ASCENDING)], unique=True)
    # 031-semantic-layer-chat — pre-existing gap found while auditing the data
    # layer (research.md R8): queried by ticker like its sibling cache
    # collections, but had no index beyond _id until now. Written by
    # agent-runner; backend only reads, but declares the same index per
    # constitution VI.
    db[INSTITUTIONAL_CACHE].create_index([("ticker", ASCENDING)], unique=True)
    # 031-semantic-layer-chat — single-field indexes only. Generated chat queries
    # combine these predicates in unpredictable orders, so a compound index would
    # serve one ordering and be ignored by the rest (research.md R8); at 15x scale
    # (~8,340 docs / ~17MB) the collection is cache-resident and index
    # intersection is ample.
    db[SCREENER].create_index([("ticker", ASCENDING)], unique=True)
    db[SCREENER].create_index([("range_pct_20d", ASCENDING)])
    db[SCREENER].create_index([("zscore_20d", ASCENDING)])
    db[SCREENER].create_index([("weekly_change_pct", ASCENDING)])
    db[SCREENER].create_index([("financials_trend", ASCENDING)])
    db[SCREENER].create_index([("fcf_exceeds_debt", ASCENDING)])
    db[SCREENER].create_index([("sector", ASCENDING)])
    db[SCREENER].create_index([("is_tracked", ASCENDING)])
    # 033-strategy-picks-filters — same single-field convention as the rest
    # of SCREENER's indexes above.
    db[SCREENER].create_index([("liked_status", ASCENDING)])
    # 032-weekly-strategy-picks — compound, unlike SCREENER's single-field
    # indexes: queried by exactly one deterministic code path
    # (semantic/strategy_picks.py) with a fixed predicate/sort shape per
    # strategy, not by unpredictable LLM-generated pipelines.
    db[STRATEGY_SIGNALS].create_index([("ticker", ASCENDING)], unique=True)
    db[STRATEGY_SIGNALS].create_index(
        [("the_strat.direction", ASCENDING), ("the_strat.strength", DESCENDING)]
    )
    db[STRATEGY_SIGNALS].create_index(
        [("gap_analysis.direction", ASCENDING), ("gap_analysis.score", DESCENDING)]
    )
    # 035-chat-and-news-upgrade — data-model.md §1. No TTL: the 30-day launch
    # backfill is the archive this feature exists to make searchable, not a
    # rolling cache.
    db[NEWS_ARTICLES].create_index([("url", ASCENDING)], unique=True)
    db[NEWS_ARTICLES].create_index([("published_at", DESCENDING)])
    db[NEWS_ARTICLES].create_index([("tickers", ASCENDING)])
    db[NEWS_ARTICLES].create_index([("source_type", ASCENDING)])
    db[NEWS_ARTICLES].create_index([("title", TEXT), ("body_text", TEXT)])
    # 035-chat-and-news-upgrade US5 — data-model.md §2. Sidebar ordering only.
    db[CHAT_CONVERSATIONS].create_index([("updated_at", DESCENDING)])
    # 036-news-semantic-search — news_tags: `_id` IS the normalized tag
    # (natural key), so its implicit unique index is the only one needed —
    # match_question_tags() loads every row's {_id, embedding, embedding_model}
    # once per semantic question and matches in NumPy (data-model.md §2, same
    # brute-force rationale as the candidate ranker). No secondary index until
    # the registry exceeds ~50k rows. The collection is created lazily on the
    # first upsert by agent-runner; no bootstrap call is needed here.
    # 037-stocks-conviction-and-activity — data-model.md §2. First index backs
    # the global activity feed (newest-first, capped at 100); second backs the
    # per-stock change-history trail; third guards the "one added event per
    # ticker" invariant.
    db[STOCK_EVENTS].create_index([("occurred_at", DESCENDING)])
    db[STOCK_EVENTS].create_index([("ticker", ASCENDING), ("occurred_at", DESCENDING)])
    db[STOCK_EVENTS].create_index([("ticker", ASCENDING), ("event_type", ASCENDING)])
