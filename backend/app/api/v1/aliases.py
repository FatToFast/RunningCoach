"""API route aliases for backward compatibility and legacy support.

This module provides:
1. Deprecated route aliases (redirect to canonical paths)
2. Legacy endpoint support for API versioning
3. Route documentation for deprecation timeline

Deprecation Policy:
- Deprecated routes return 301 redirect to canonical path
- Deprecation warnings are included in response headers
- Legacy routes are maintained for 2 major versions before removal

Usage:
    Include alias_router in main API router to enable legacy support.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

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
        # Build full canonical URL
        full_canonical = f"/api/v1{canonical_path}"

        # Add query parameters if present
        if request.url.query:
            full_canonical = f"{full_canonical}?{request.url.query}"

        # Set deprecation headers
        response.headers[DEPRECATION_HEADER] = (
            f"This endpoint is deprecated. Use {full_canonical} instead. "
            f"Will be removed in {removal_version}."
        )

        return RedirectResponse(
            url=full_canonical,
            status_code=status.HTTP_308_PERMANENT_REDIRECT,
        )

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


@alias_router.get("/aliases", response_model=AliasListResponse)
async def list_aliases() -> AliasListResponse:
    """List all route aliases and their deprecation status.

    Returns:
        List of route aliases with deprecation information.
    """
    now = datetime.now()
    aliases = []

    for deprecated, canonical, dep_date, removal_ver in ROUTE_ALIASES:
        # Determine status based on dates
        dep_datetime = datetime.fromisoformat(dep_date)
        if now > dep_datetime:
            alias_status = "deprecated"
        else:
            alias_status = "active"

        aliases.append(
            AliasInfo(
                deprecated_path=deprecated,
                canonical_path=canonical,
                deprecation_date=dep_date,
                removal_version=removal_ver,
                status=alias_status,
            )
        )

    return AliasListResponse(
        aliases=aliases,
        current_version="v1",
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
