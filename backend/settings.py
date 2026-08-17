from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "stockai"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    finnhub_api_key: str = ""  # earnings calendar fetch (routers/earnings.py)
    fmp_api_key: str = ""  # price chart fetch (routers/price.py)
    # Shared daily budget with agent-runner (same name/default there). 0 = disabled.
    fmp_daily_soft_cap: int = 0


settings = Settings()
