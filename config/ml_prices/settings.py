from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class MLPricesSettings(BaseSettings):
    """Runtime configuration for the Mercado Livre Playwright scraper."""

    pages_to_scrape: int = Field(default=3, ge=1)
    headless: bool = Field(default=True)
    page_load_timeout: int = Field(default=40, ge=1)
    explicit_wait: int = Field(default=20, ge=1)

    class Config:
        env_prefix = "ML_PRICES_"
        env_file_encoding = "utf-8"


def get_settings(env_file: Optional[str] = None) -> MLPricesSettings:
    """
    Return a settings instance from the specified env file.
    
    Args:
        env_file: Path to the .env file. If None, uses 'config/.env' by default.
    
    Examples:
        get_settings()                      # uses config/.env
        get_settings("config/.env.test")    # uses config/.env.test
        get_settings("config/.env.dev")     # uses config/.env.dev
    """
    if env_file is None:
        env_file = "config/.env"
    
    return MLPricesSettings(_env_file=env_file)


# Default instance for production use
settings = get_settings()