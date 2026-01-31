from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class MaxBidSettings(BaseSettings):
    """Runtime configuration for the Max Bid service."""

    dev_mode_simples_nacional_base_tax: float = Field(default=0.04)

    class Config:
        env_prefix = "MAX_BID_"
        env_file_encoding = "utf-8"

def get_settings(env_file: Optional[str] = None) -> MaxBidSettings:
    """
    Return a settings instance from the specified env file.
    """
    if env_file is None:
        env_file = "config/.env"
    return MaxBidSettings(_env_file=env_file)