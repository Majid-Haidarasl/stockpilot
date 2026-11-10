"""Application settings loaded from environment."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_name: str = "stockpilot"
    environment: str = "development"

    # Runtime DB role only (never the schema owner in default Compose).
    database_url: str = Field(
        default="postgresql+psycopg://stockpilot_app:changeme@postgres:5432/stockpilot",
        alias="STOCKPILOT_DATABASE_URL",
    )
    expected_schema_revision: str = Field(
        default="0001_schemas",
        alias="STOCKPILOT_EXPECTED_SCHEMA_REVISION",
    )


def get_settings() -> Settings:
    return Settings()
