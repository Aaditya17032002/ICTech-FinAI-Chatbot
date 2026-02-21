from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str = ""
    
    router_model: str = "groq/compound-beta"
    analyst_model: str = "groq/meta-llama/llama-4-scout-17b-16e-instruct"
    reasoning_model: str = "groq/qwen/qwen3-32b"
    
    database_url: str = "sqlite:///./data/investment.db"
    cache_dir: str = "./data/cache"
    cache_ttl_hours: int = 24
    
    log_level: str = "INFO"
    
    app_name: str = "Investment Insight Chatbot"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
