from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class MLPricesSettings(BaseSettings):
    """Runtime configuration for ML Prices with LLM support."""

    # Scraper settings
    pages_to_scrape: int = Field(default=3, ge=1)
    headless: bool = Field(default=True)
    page_load_timeout: int = Field(default=40, ge=1)
    explicit_wait: int = Field(default=20, ge=1)

    # Ollama settings
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen3:4b")
    ollama_timeout: float = Field(default=120.0)
    ollama_temperature: float = Field(default=0.1)

    # Analysis settings
    min_relevant_ratio: float = Field(
        default=0.3,
        ge=0.0, le=1.0,
        description="Minimum ratio of relevant results before suggesting new key"
    )
    max_search_retries: int = Field(
        default=3,
        ge=1,
        description="Maximum number of search key refinements"
    )

    class Config:
        env_prefix = "ML_PRICES_"
        env_file_encoding = "utf-8"


def get_settings(env_file: Optional[str] = None) -> MLPricesSettings:
    """
    Return a settings instance from the specified env file.

    Args:
        env_file: Path to the .env file. If None, uses 'config/.env' by default.
    """
    if env_file is None:
        env_file = "config/.env"

    return MLPricesSettings(_env_file=env_file)


settings = get_settings()
