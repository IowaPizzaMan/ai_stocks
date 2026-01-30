from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    sentiment_model: str = "ahmedrachid/FinancialBERT-Sentiment-Analysis"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    backend_url: str = "http://localhost:8000"
    host: str = "0.0.0.0"
    port: int = 8001

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
