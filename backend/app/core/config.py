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

    # FIT file management policy
    delete_fit_after_parse: bool = True  # Delete FIT file after successful parse (data saved to DB)
    fit_min_samples_for_delete: int = 10  # Minimum ActivitySample records required before deleting FIT

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

    # AI Provider (google or openai)
    ai_provider: str = "google"  # "google" or "openai"

    # AI Snapshot settings
    ai_snapshot_weeks: int = 6  # Default snapshot window (weeks)
    ai_snapshot_recovery_days: int = 7  # Recovery metrics lookback (days)
    ai_snapshot_all_time_start_year: int = 2006  # Earliest year for "all-time" queries
    ai_default_interval_pace: int = 270  # Default interval pace (sec/km) - 4:30/km
    ai_default_tempo_pace: int = 300  # Default tempo pace (sec/km) - 5:00/km
    ai_sample_limit: int = 5000  # Max samples to analyze for FIT data

    # Gear settings
    gear_default_max_distance_meters: int = 800_000  # Default max distance for shoes (800km)

    # Strava HTTP timeout settings
    strava_http_timeout_seconds: int = 60  # HTTP timeout for upload requests
    strava_http_timeout_short_seconds: int = 30  # HTTP timeout for token/status requests
    strava_token_refresh_buffer_seconds: int = 300  # Refresh token 5 min before expiry

    # Google AI (Gemini)
    google_ai_api_key: Optional[str] = None
    google_ai_model: str = "gemini-2.5-flash-lite"

    # OpenAI (legacy, fallback)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_budget_usd: Optional[float] = None

    # AI Coach settings
    ai_default_language: str = "ko"
    ai_max_history_messages: int = 20
    ai_snapshot_weeks: int = 12  # Training snapshot window
    ai_snapshot_recovery_days: int = 7  # Recovery period
    ai_default_interval_pace: int = 270  # 4:30/km in seconds (user-adjustable)
    ai_default_tempo_pace: int = 300  # 5:00/km in seconds (user-adjustable)

    # AI Model parameters
    ai_max_tokens: int = 2000  # Maximum tokens for AI responses
    ai_temperature_chat: float = 0.7  # Temperature for chat responses (0.0-1.0)
    ai_temperature_plan: float = 0.5  # Temperature for plan generation (lower for more deterministic)

    # Token cost estimation (per 1K tokens)
    ai_token_cost_google: float = 0.00075  # Gemini pricing
    ai_token_cost_openai: float = 0.002  # GPT-4o pricing

    # RAG (Retrieval-Augmented Generation) settings
    rag_enabled: bool = True
    rag_top_k: int = 3
    rag_min_score: float = 0.3
    rag_max_context_length: int = 3000

    # Embedding settings (for RAG)
    embedding_provider: str = "google"  # "google" or "openai"
    google_embedding_model: str = "text-embedding-004"
    openai_embedding_model: str = "text-embedding-3-small"

    # Localization
    default_timezone: str = "Asia/Seoul"

    # Strava
    strava_client_id: Optional[str] = None
    strava_client_secret: Optional[str] = None
    strava_redirect_uri: Optional[str] = None
    strava_encryption_key: Optional[str] = None  # Fernet key for encrypting tokens
    strava_oauth_base_url: str = "https://www.strava.com/oauth"  # OAuth endpoints
    strava_api_base_url: str = "https://www.strava.com/api/v3"  # API endpoints
    strava_token_refresh_buffer_seconds: int = 300  # Refresh token 5 min before expiry
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
    sync_lock_ttl_seconds: int = 10800  # 3 hours (for large backfills)
    sync_lock_extension_interval: int = 600  # Extend lock every 10 minutes during sync

    # Observability
    metrics_backend: str = "inmemory"  # "inmemory" | "prometheus"
    otel_enabled: bool = False
    otel_service_name: str = "runningcoach-api"
    otel_exporter_otlp_endpoint: Optional[str] = None

    # Admin (initial seed account)
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    admin_display_name: Optional[str] = None

    # ======================
    # Cloud Services (Clerk + Neon + R2)
    # ======================

    # Clerk Authentication
    clerk_publishable_key: Optional[str] = None
    clerk_secret_key: Optional[str] = None
    clerk_webhook_secret: Optional[str] = None

    @property
    def clerk_frontend_api(self) -> Optional[str]:
        """Extract Clerk frontend API domain from publishable key.

        Clerk publishable key format: pk_test_XXX or pk_live_XXX
        where XXX is base64-encoded "domain$" (domain with trailing $).
        Example: pk_test_Y2xlcmsuZXhhbXBsZS5jb20k -> clerk.example.com
        """
        if not self.clerk_publishable_key:
            return None
        try:
            import base64
            parts = self.clerk_publishable_key.split('_')
            if len(parts) >= 3:
                encoded_domain = parts[2]
                # Add padding if needed for base64
                padding = 4 - len(encoded_domain) % 4
                if padding != 4:
                    encoded_domain += '=' * padding
                decoded = base64.b64decode(encoded_domain).decode('utf-8')
                # Remove trailing $ marker
                return decoded.rstrip('$')
        except Exception:
            pass
        return None

    @property
    def clerk_jwks_url(self) -> Optional[str]:
        """Get Clerk JWKS URL from publishable key."""
        domain = self.clerk_frontend_api
        if domain:
            return f"https://{domain}/.well-known/jwks.json"
        return None

    @property
    def clerk_issuer(self) -> Optional[str]:
        """Get Clerk JWT issuer URL for token validation."""
        domain = self.clerk_frontend_api
        if domain:
            return f"https://{domain}"
        return None

    @property
    def clerk_enabled(self) -> bool:
        """Check if Clerk authentication is configured."""
        return bool(self.clerk_publishable_key and self.clerk_secret_key)

    # Cloudflare R2 Storage
    r2_account_id: Optional[str] = None
    r2_access_key: Optional[str] = None
    r2_secret_key: Optional[str] = None
    r2_bucket_name: str = "fit-files"

    @property
    def r2_endpoint_url(self) -> Optional[str]:
        """Get R2 endpoint URL."""
        if not self.r2_account_id:
            return None
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def r2_enabled(self) -> bool:
        """Check if R2 storage is configured."""
        return bool(self.r2_account_id and self.r2_access_key and self.r2_secret_key)

    # Neon Database (uses database_url, just add helper property)
    @property
    def is_neon_database(self) -> bool:
        """Check if using Neon database."""
        return "neon.tech" in self.database_url if self.database_url else False

    # Cloud deployment mode
    cloud_mode: bool = False  # Set to True to enable cloud services

    @property
    def is_cloud_deployment(self) -> bool:
        """Check if running in cloud deployment mode."""
        return self.cloud_mode or (self.clerk_enabled and self.r2_enabled)


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
