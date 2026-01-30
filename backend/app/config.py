from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/aistock"
    ai_models_url: str = "http://localhost:8001"
    ollama_url: str = "http://localhost:11434"
    ai_models_enabled: bool = False  # Set to True if running ai_models service

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
