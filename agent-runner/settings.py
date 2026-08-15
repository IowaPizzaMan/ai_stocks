from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "stockai"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    fred_api_key: str = ""

    # Paid-tier throttle: Starter allows 300/min, we cap at 250 for headroom.
    # Soft cap is a secondary daily ceiling, off by default; set to 225 to
    # survive a downgrade back to the free tier (250/day) without code changes.
    fmp_calls_per_minute: int = 250
    fmp_daily_soft_cap: int = 0  # 0 = disabled

    queue_poll_seconds: int = 30
    institutional_scan_hour_utc: int = 22  # daily market-wide scan, after US close
    breadth_refresh_hour_utc: int = 21  # NYMO/NAMO + divergence sweep, after US close


settings = Settings()
