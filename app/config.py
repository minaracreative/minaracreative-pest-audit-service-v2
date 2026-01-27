"""Configuration management using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_maps_api_key: str = Field(validation_alias="GOOGLE_MAPS_API_KEY")
    serpapi_api_key: str = Field(validation_alias="SERPAPI_API_KEY")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    cache_ttl_hours: int = Field(default=24, validation_alias="CACHE_TTL_HOURS")


settings = Settings()
