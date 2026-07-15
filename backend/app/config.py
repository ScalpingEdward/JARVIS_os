from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JARVIS OS"
    environment: str = "development"
    version: str = "0.1.0"
    database_url: str = "sqlite:///./jarvis.db"

    anthropic_enabled: bool = False
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"

    openai_enabled: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
