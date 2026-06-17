"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/analytics_db"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@db:5432/analytics_db"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Application
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # Data Generation
    SEED: int = 42
    CUSTOMERS_COUNT: int = 100_000
    ORDERS_COUNT: int = 1_000_000
    REFUNDS_COUNT: int = 200_000

    # Mock API (127.0.0.1 works reliably inside Docker containers)
    MOCK_API_BASE_URL: str = "http://127.0.0.1:8000"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 1000
    MAX_PAGE_SIZE: int = 5000

    # Ingestion
    INGESTION_BATCH_SIZE: int = 5000
    INGESTION_CONCURRENCY: int = 10

    # Cache
    CACHE_TTL_SECONDS: int = 60


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
