"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Centralized settings — sourced from environment variables / .env file."""

    model_config = SettingsConfigDict(
        # Look for .env at backend/.env first, then repo root .env
        env_file=(str(_REPO_ROOT / ".env"), str(_REPO_ROOT / "backend" / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str = Field(default="", description="OpenAI API key")
    default_openai_model: str = Field(default="gpt-4o-mini")

    database_url: str = Field(
        default="postgresql+asyncpg://orchestra:orchestra@localhost:5432/orchestra",
        description="Async SQLAlchemy URL for application data",
    )
    langgraph_database_url: str = Field(
        default="postgresql://orchestra:orchestra@localhost:5432/orchestra",
        description="psycopg3 URL for the LangGraph checkpointer",
    )

    redis_url: str = Field(default="redis://localhost:6379/0")

    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    telegram_bot_token: str = Field(default="", description="Optional Telegram bot token")

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
