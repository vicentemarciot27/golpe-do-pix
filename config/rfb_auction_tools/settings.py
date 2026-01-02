from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class RFBAuctionSettings(BaseSettings):
    """Runtime configuration for the RFB Auction collector."""

    base_url: str = Field(
        default="http://www25.receita.fazenda.gov.br/sle-sociedade/api"
    )
    request_timeout: int = Field(default=30, ge=1)
    test_mode: bool = Field(default=False)
    request_delay: float = Field(default=0.0, ge=0.0)
    max_retries: int = Field(default=2, ge=1)
    retry_backoff_base: float = Field(default=2.0, ge=1.0)

    class Config:
        env_prefix = "RFB_AUCTION_"
        env_file_encoding = "utf-8"


def get_settings(env_file: Optional[str] = None) -> RFBAuctionSettings:
    """
    Return a settings instance from the specified env file.

    Args:
        env_file: Path to the .env file. If None, uses 'config/.env' by default.

    Examples:
        get_settings()                      # uses config/.env
        get_settings("config/.env.test")    # uses config/.env.test
    """
    if env_file is None:
        env_file = "config/.env"

    return RFBAuctionSettings(_env_file=env_file)
