from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings



class MLPricesSettings(BaseSettings):
    """Runtime configuration for the Mercado Livre Playwright scraper."""

    pages_to_scrape: int = Field(default=3, ge=1)
    headless: bool = Field(default=False)
    page_load_timeout: int = Field(default=40, ge=1)  # segundos
    explicit_wait: int = Field(default=20, ge=1)  # segundos

    class Config:
        env_prefix = "ML_PRICES_"
        env_file = "config/.env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> MLPricesSettings:
    """Return a cached settings instance to avoid re-reading env vars."""
    return MLPricesSettings()


settings = get_settings()
