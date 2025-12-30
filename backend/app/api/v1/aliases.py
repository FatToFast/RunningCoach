"""API route aliases for backward compatibility and legacy support.

This module provides:
1. Deprecated route aliases (redirect to canonical paths)
2. Legacy endpoint support for API versioning
3. Route documentation for deprecation timeline

Deprecation Policy:
- Deprecated routes return 308 Permanent Redirect to canonical path
- Deprecation warnings are included in response headers (X-API-Deprecation-Warning)
- Legacy routes are maintained for 2 major versions before removal

Usage:
    Include alias_router in main API router to enable legacy support.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()

# -------------------------------------------------------------------------
# Alias Configuration
# -------------------------------------------------------------------------

# Format: (deprecated_path, canonical_path, deprecation_date, removal_version)
ROUTE_ALIASES = [
    # Garmin sync → ingest (historical naming)
    ("/sync/garmin/run", "/ingest/run", "2025-01-01", "v2.0"),
    ("/sync/garmin/status", "/ingest/status", "2025-01-01", "v2.0"),
    # Data endpoints aliases
    ("/data/activities", "/activities", "2025-01-01", "v2.0"),
    ("/data/sleep", "/sleep", "2025-01-01", "v2.0"),
    ("/data/hr", "/hr", "2025-01-01", "v2.0"),
    # Dashboard aliases
    ("/stats/summary", "/dashboard/summary", "2025-01-01", "v2.0"),
    ("/stats/trends", "/dashboard/trends", "2025-01-01", "v2.0"),
    # Strava sync aliases
    ("/strava/upload", "/strava/sync/run", "2025-01-01", "v2.0"),
]

# Headers for deprecation warnings
DEPRECATION_HEADER = "X-API-Deprecation-Warning"
SUNSET_HEADER = "Sunset"


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class AliasInfo(BaseModel):
    """Information about a route alias."""

    deprecated_path: str
    canonical_path: str
    deprecation_date: str
    removal_version: str
    status: str  # "deprecated", "active", "removed"


class AliasListResponse(BaseModel):
    """List of all route aliases."""

    aliases: list[AliasInfo]
    current_version: str
    deprecation_policy: str


# -------------------------------------------------------------------------
# Alias Router
# -------------------------------------------------------------------------

alias_router = APIRouter(tags=["aliases"])


def create_redirect_handler(deprecated_path: str, canonical_path: str, removal_version: str):
    """Create a redirect handler for a deprecated route.

    Args:
        deprecated_path: The deprecated route path.
        canonical_path: The canonical route path to redirect to.
        removal_version: Version when the deprecated route will be removed.

    Returns:
        Route handler function.
    """

    async def redirect_handler(
        request: Request,
        response: Response,
    ) -> RedirectResponse:
        """Redirect deprecated route to canonical path with deprecation warning."""
        # Build full canonical URL using settings.api_prefix
        full_canonical = f"{settings.api_prefix}{canonical_path}"

        # Add query parameters if present
        if request.url.query:
            full_canonical = f"{full_canonical}?{request.url.query}"

        # Create redirect response with deprecation headers
        # Note: Headers must be set on RedirectResponse itself, not the injected response
        redirect = RedirectResponse(
            url=full_canonical,
            status_code=status.HTTP_308_PERMANENT_REDIRECT,
        )
        redirect.headers[DEPRECATION_HEADER] = (
            f"This endpoint is deprecated. Use {full_canonical} instead. "
            f"Will be removed in {removal_version}."
        )

        return redirect

    return redirect_handler


# Register alias redirects dynamically
for deprecated, canonical, dep_date, removal_ver in ROUTE_ALIASES:
    handler = create_redirect_handler(deprecated, canonical, removal_ver)

    # Register for all common HTTP methods
    for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
        alias_router.add_api_route(
            deprecated,
            handler,
            methods=[method],
            include_in_schema=False,  # Hide from OpenAPI docs
            response_class=RedirectResponse,
        )


# -------------------------------------------------------------------------
# Alias Documentation Endpoint
# -------------------------------------------------------------------------


def _get_current_api_version() -> str:
    """Extract current API version from settings.api_prefix.

    Examples:
        "/api/v1" -> "v1"
        "/api/v2" -> "v2"
    """
    prefix = settings.api_prefix
    # Extract version from prefix like "/api/v1"
    if prefix and "/" in prefix:
        return prefix.rstrip("/").split("/")[-1]
    return "v1"


def _parse_version(version_str: str) -> tuple[int, int]:
    """Parse version string like 'v2.0' into (major, minor) tuple."""
    version_str = version_str.lstrip("v")
    parts = version_str.split(".")
    major = int(parts[0]) if parts else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    return (major, minor)


@alias_router.get("/aliases", response_model=AliasListResponse)
async def list_aliases() -> AliasListResponse:
    """List all route aliases and their deprecation status.

    Returns:
        List of route aliases with deprecation information.
    """
    now = datetime.now()
    current_version = _get_current_api_version()
    current_ver_tuple = _parse_version(current_version)
    aliases = []

    for deprecated, canonical, dep_date, removal_ver in ROUTE_ALIASES:
        # Determine status based on dates and version
        dep_datetime = datetime.fromisoformat(dep_date)
        removal_ver_tuple = _parse_version(removal_ver)

        if current_ver_tuple >= removal_ver_tuple:
            # Current version >= removal version: route is removed
            alias_status = "removed"
        elif now > dep_datetime:
            # Past deprecation date but not yet removed
            alias_status = "deprecated"
        else:
            # Before deprecation date
            alias_status = "active"

        aliases.append(
            AliasInfo(
                deprecated_path=deprecated,
                canonical_path=f"{settings.api_prefix}{canonical}",
                deprecation_date=dep_date,
                removal_version=removal_ver,
                status=alias_status,
            )
        )

    return AliasListResponse(
        aliases=aliases,
        current_version=current_version,
        deprecation_policy=(
            "Deprecated routes are maintained for 2 major versions. "
            "Use canonical paths for long-term stability."
        ),
    )


# -------------------------------------------------------------------------
# Version Negotiation Middleware (Optional)
# -------------------------------------------------------------------------


class VersionNegotiator:
    """Handle API version negotiation via headers or path."""

    SUPPORTED_VERSIONS = ["v1"]
    DEFAULT_VERSION = "v1"

    @classmethod
    def get_version(
        cls,
        accept_version: str | None = Header(None, alias="Accept-Version"),
    ) -> str:
        """Extract API version from headers or use default.

        Args:
            accept_version: Optional version header.

        Returns:
            API version string.

        Raises:
            HTTPException: If requested version is not supported.
        """
        if not accept_version:
            return cls.DEFAULT_VERSION

        if accept_version not in cls.SUPPORTED_VERSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported API version: {accept_version}. "
                f"Supported versions: {cls.SUPPORTED_VERSIONS}",
            )

        return accept_version
