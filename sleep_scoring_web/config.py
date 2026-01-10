"""
Application configuration using Pydantic Settings.

Single source of configuration for the web application.
Loads from environment variables with .env file support.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from global_auth import AuthSettingsMixin
from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(AuthSettingsMixin, BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Sleep Scoring Web"
    app_version: str = "0.1.0"
    debug: bool = False
    sql_echo: bool = False  # Log all SQL statements (very verbose, disable by default)
    environment: Literal["development", "staging", "production"] = "development"

    # API Settings
    api_prefix: str = "/api/v1"  # Standardized prefix matching other apps
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"])

    # Rate Limiting
    rate_limit_default: str = "100/minute"
    rate_limit_upload: str = "60/minute"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated string into list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Session settings (custom for this app)
    session_expire_hours: int = 24 * 7  # 1 week default

    # Database - PostgreSQL (primary)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "sleep_scoring"
    postgres_password: str = "sleep_scoring"
    postgres_db: str = "sleep_scoring"

    # Database - SQLite (backup/development)
    sqlite_path: str = "sleep_scoring_web.db"
    use_sqlite: bool = True  # Use SQLite for development, PostgreSQL for production

    # File Upload
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 100
    upload_api_key: str = ""  # API key for programmatic uploads (pipeline integration)

    # Data directory - use POST /api/v1/files/scan to import files
    data_dir: str = "data"
    scan_data_dir_on_startup: bool = False  # Never block startup - use background tasks

    # Data Processing
    default_epoch_length: int = 60
    default_skip_rows: int = 10

    @computed_field
    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL connection string."""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @computed_field
    @property
    def sqlite_dsn(self) -> str:
        """Build SQLite connection string."""
        return f"sqlite+aiosqlite:///{self.sqlite_path}"

    @computed_field
    @property
    def database_url(self) -> str:
        """Get the active database URL based on configuration."""
        if self.use_sqlite:
            return self.sqlite_dsn
        return self.postgres_dsn


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
