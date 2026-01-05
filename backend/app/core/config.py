"""Application configuration settings."""

import logging
import os
import warnings
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Environment detection
_ENV = os.environ.get("ENVIRONMENT", "development").lower()
_IS_PRODUCTION = _ENV in ("production", "prod")


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
    api_prefix: str = "/api/v1"  # Must NOT have trailing slash

    @property
    def normalized_api_prefix(self) -> str:
        """Return api_prefix with trailing slash removed."""
        return self.api_prefix.rstrip("/")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/runningcoach"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Session
    session_secret: str = "change-me-in-production"
    session_ttl_seconds: int = 604800  # 7 days
    session_cookie_name: str = "session_id"  # Cookie name for session ID
    cookie_secure: bool = False  # Set to True in production (HTTPS)
    cookie_samesite: str = "lax"  # Starlette expects lowercase: "lax", "strict", "none"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

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
    garmin_max_consecutive_empty: int = 30  # Stop backfill after N empty days

    # FIT Storage (default to ./data/fit for local dev, override in production)
    fit_storage_path: str = "./data/fit_files"

    @property
    def fit_storage_path_absolute(self) -> str:
        """Get absolute path for FIT storage.

        Resolves relative paths based on the backend directory to ensure
        consistent behavior across different working directories.
        """
        if os.path.isabs(self.fit_storage_path):
            return self.fit_storage_path
        # Resolve relative to backend directory (where app/ is located)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(backend_dir, self.fit_storage_path)

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_budget_usd: Optional[float] = None

    # AI Coach settings
    ai_default_language: str = "ko"
    ai_max_history_messages: int = 20

    # Localization
    default_timezone: str = "Asia/Seoul"

    # Strava
    strava_client_id: Optional[str] = None
    strava_client_secret: Optional[str] = None
    strava_redirect_uri: Optional[str] = None
    strava_auto_upload: bool = True  # Auto-upload to Strava after Garmin sync
    strava_upload_concurrency: int = 3  # Max concurrent uploads
    strava_upload_retry_delays: str = "60,300,1800,7200"  # Retry delays in seconds (1m, 5m, 30m, 2h)
    strava_upload_max_retries: int = 4

    # Runalyze
    runalyze_api_token: Optional[str] = None
    runalyze_api_base_url: str = "https://runalyze.com/api/v1"
    runalyze_username: Optional[str] = None
    runalyze_password: Optional[str] = None

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


_INSECURE_DEFAULT = "change-me-in-production"


class InsecureConfigurationError(Exception):
    """Raised when insecure configuration is detected in production."""

    pass


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    In production (ENVIRONMENT=production), raises InsecureConfigurationError
    if security-sensitive settings are using default values.
    In development, logs warnings instead.
    """
    settings = Settings()

    insecure_settings: list[str] = []

    # Check session_secret
    if settings.session_secret == _INSECURE_DEFAULT:
        insecure_settings.append("SESSION_SECRET")

    # Check secret_key
    if settings.secret_key == _INSECURE_DEFAULT:
        insecure_settings.append("SECRET_KEY")

    # Check database_url (default contains 'localhost')
    if "localhost" in settings.database_url and _IS_PRODUCTION:
        insecure_settings.append("DATABASE_URL (using localhost in production)")

    if insecure_settings:
        msg = (
            f"Insecure configuration detected: {', '.join(insecure_settings)}. "
            "Set these environment variables before running in production."
        )
        if _IS_PRODUCTION:
            # In production, fail fast - don't allow insecure defaults
            raise InsecureConfigurationError(msg)
        else:
            # In development, warn but continue
            logger.warning(msg)
            warnings.warn(msg, UserWarning, stacklevel=2)

    return settings
