from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The root .env / docker-compose.yml set these without the JARVIS_
    # prefix (matching common tooling conventions -- APP_NAME, DATABASE_URL,
    # etc.), while backend/.env (local dev/tests) sets the JARVIS_-prefixed
    # form. AliasChoices accepts either, JARVIS_ first, so both keep working.
    app_name: str = Field(
        default="JARVIS OS", validation_alias=AliasChoices("JARVIS_APP_NAME", "APP_NAME")
    )
    environment: str = Field(
        default="development", validation_alias=AliasChoices("JARVIS_ENVIRONMENT", "ENVIRONMENT")
    )
    version: str = "0.1.0"
    # docker-compose.yml and .env set this as plain DATABASE_URL (matching
    # the common Postgres-tooling convention), not JARVIS_DATABASE_URL --
    # the explicit alias makes this field read that instead of silently
    # falling back to the sqlite default. See backend/app/db.py.
    database_url: str = Field(default="sqlite:///./jarvis.db", validation_alias="DATABASE_URL")

    anthropic_enabled: bool = False
    anthropic_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("JARVIS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")
    )
    anthropic_model: str = "claude-sonnet-4-5"

    openai_enabled: bool = False
    openai_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("JARVIS_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    openai_model: str = "gpt-5-mini"

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
