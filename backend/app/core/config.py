"""Application configuration settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "RunningCoach"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/runningcoach"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Session
    session_secret: str = "change-me-in-production"
    session_ttl_seconds: int = 604800  # 7 days
    cookie_secure: bool = True
    cookie_samesite: str = "Lax"

    # Security (legacy JWT - can be removed if not needed)
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Garmin
    garmin_email: Optional[str] = None
    garmin_password: Optional[str] = None
    garmin_encryption_key: Optional[str] = None
    garmin_backfill_days: int = 0  # 0 = full history
    garmin_safety_window_days: int = 3

    # FIT Storage
    fit_storage_path: str = "/data/fit"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_budget_usd: Optional[float] = None

    # Strava
    strava_client_id: Optional[str] = None
    strava_client_secret: Optional[str] = None
    strava_redirect_uri: Optional[str] = None

    # Runalyze
    runalyze_api_token: Optional[str] = None
    runalyze_api_base_url: str = "https://runalyze.com/api/v1"

    # Sync
    sync_cron: Optional[str] = None  # e.g., "0 */6 * * *" for every 6 hours

    # Observability
    metrics_backend: str = "inmemory"  # "inmemory" | "prometheus"
    otel_enabled: bool = False
    otel_service_name: str = "runningcoach-api"
    otel_exporter_otlp_endpoint: Optional[str] = None

    # Admin (initial seed account)
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    admin_display_name: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
