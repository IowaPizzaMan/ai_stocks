from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "stockai"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"

    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    fred_api_key: str = ""

    # Paid-tier throttle: Starter allows 300/min, we cap at 250 for headroom.
    # Soft cap is a secondary daily ceiling, off by default; set to 225 to
    # survive a downgrade back to the free tier (250/day) without code changes.
    fmp_calls_per_minute: int = 300
    fmp_daily_soft_cap: int = 0  # 0 = disabled

    queue_poll_seconds: int = 30
    institutional_scan_hour_utc: int = 22  # daily market-wide scan, after US close
    breadth_refresh_hour_utc: int = 21  # NYMO/NAMO + divergence sweep, after US close
    economics_refresh_hour_utc: int = 22  # treasury/calendar/indicators/risk-premium pull

    # 036-news-semantic-search — per-article enrichment tunables
    # (data-model.md §6). `ollama_embed_model` / `news_embed_max_chars` mirror
    # backend/settings.py (shared by build_embed_text, hand-copied per
    # constitution V). `news_enrich_batch_per_run` paces the archive backfill
    # (research.md R7) and is agent-runner-only.
    ollama_embed_model: str = "nomic-embed-text"  # FR-013 swap point
    news_embed_max_chars: int = 2000  # R10 head-truncation before embedding
    news_enrich_batch_per_run: int = 200  # R7 backfill pacing


settings = Settings()
