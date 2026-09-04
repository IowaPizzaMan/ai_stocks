from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "stockai"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"

    fmp_api_key: str = ""  # price chart fetch (routers/price.py)
    # Shared daily budget with agent-runner (same name/default there). 0 = disabled.
    fmp_daily_soft_cap: int = 0

    # chat (specs/031-semantic-layer-chat) — agent-runner/llm.py passes no
    # timeout anywhere (KNOWN_ISSUES.md); an HTTP request handler calling the
    # model needs one so a stalled generation can't hang the request forever.
    chat_ollama_timeout_seconds: float = 30.0
    # Keeps qwen3:14b resident between questions — research.md R2 measured
    # ~10s of model-load time on a cold call, which alone would miss SC-001's
    # 10-second target on every session's first question.
    chat_ollama_keep_alive: str = "30m"

    # 036-news-semantic-search — semantic news retrieval + ranking tunables
    # (data-model.md §6). `ollama_embed_model` and `news_embed_max_chars` are
    # mirrored in agent-runner/settings.py (shared by build_embed_text);
    # the news_rank_* knobs are backend-only (the ranker lives here).
    ollama_embed_model: str = "nomic-embed-text"  # FR-013 swap point
    news_embed_max_chars: int = 2000  # R10 head-truncation before embedding
    news_rank_half_life_days: float = 14.0  # R6 recency decay (FR-004a)
    news_rank_max_candidates: int = 5000  # R3/R4 brute-force pool cap
    news_rank_fallback_days: int = 30  # R4 no-tag-match recency window
    news_tag_match_threshold: float = 0.72  # R5 question->tag cosine cutoff
    news_rank_min_ticker_pool: int = 3  # R4 ticker-reason -> recency fallback
    news_rank_top_n: int = 10  # grounding cap (spec FR-008)
    # Minimum raw cosine (pre recency-decay) for an article to be allowed to
    # ground an answer. Implements spec US1 AS3 / Edge Case "no stored news is
    # relevant" — without a floor the recency-window fallback (FR-006) always
    # returns the N most-recent articles at ~0 similarity, i.e. a weak
    # citation. Tunable (calibrated on the golden set, T041); a value of 0
    # disables the floor.
    news_rank_min_similarity: float = 0.25


settings = Settings()
