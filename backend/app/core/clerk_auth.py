"""Clerk authentication middleware for JWT verification.

This module provides JWT-based authentication using Clerk.
It supports both Clerk-only and hybrid authentication modes.
"""

import logging
from typing import Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Security scheme - auto_error=False allows optional auth
security = HTTPBearer(auto_error=False)

# JWKS client for token verification (lazy initialization)
_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> Optional[PyJWKClient]:
    """Get or create JWKS client singleton."""
    global _jwks_client
    if _jwks_client is None and settings.clerk_jwks_url:
        try:
            _jwks_client = PyJWKClient(settings.clerk_jwks_url)
            logger.info(f"Initialized JWKS client with URL: {settings.clerk_jwks_url}")
        except Exception as e:
            logger.error(f"Failed to initialize JWKS client: {e}")
    return _jwks_client


class ClerkAuth:
    """Clerk authentication handler with comprehensive logging."""

    @staticmethod
    async def verify_token(token: str) -> dict:
        """Verify Clerk JWT token.

        Args:
            token: JWT token from Authorization header

        Returns:
            Decoded JWT payload

        Raises:
            HTTPException: If token is invalid or Clerk not configured
        """
        jwks_client = get_jwks_client()
        if not jwks_client:
            logger.error("Clerk authentication not configured - JWKS client unavailable")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk authentication not configured"
            )

        try:
            # Get signing key from JWKS
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            logger.debug(f"Retrieved signing key for JWT verification")

            # Verify and decode token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False}  # Clerk doesn't always set audience
            )

            clerk_user_id = payload.get("sub")
            logger.info(f"JWT verified successfully for Clerk user: {clerk_user_id}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during JWT verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed"
            )

    @staticmethod
    async def get_clerk_user_data(clerk_user_id: str) -> dict:
        """Fetch user data from Clerk API.

        Args:
            clerk_user_id: Clerk user ID (sub claim from JWT)

        Returns:
            Clerk user data dictionary

        Raises:
            HTTPException: If API request fails
        """
        if not settings.clerk_secret_key:
            logger.error("Clerk secret key not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk not properly configured"
            )

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.clerk.com/v1/users/{clerk_user_id}",
                    headers={
                        "Authorization": f"Bearer {settings.clerk_secret_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    user_data = response.json()
                    logger.debug(f"Fetched Clerk user data for: {clerk_user_id}")
                    return user_data
                elif response.status_code == 404:
                    logger.warning(f"Clerk user not found: {clerk_user_id}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found in Clerk"
                    )
                else:
                    logger.error(f"Clerk API error: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Failed to fetch user data from Clerk"
                    )

            except httpx.TimeoutException:
                logger.error("Timeout connecting to Clerk API")
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Clerk API timeout"
                )
            except httpx.RequestError as e:
                logger.error(f"Error connecting to Clerk API: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to connect to Clerk API"
                )


async def get_current_user_clerk(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user from Clerk JWT token.

    This function verifies the JWT, looks up the user by clerk_user_id,
    and auto-creates the user on first login.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        User object from database

    Raises:
        HTTPException: If user not authenticated or token invalid
    """
    if not credentials:
        logger.debug("No authorization credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    # Verify token and get payload
    payload = await ClerkAuth.verify_token(token)
    clerk_user_id = payload.get("sub")

    if not clerk_user_id:
        logger.error("JWT payload missing 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload - missing user ID"
        )

    # Find user in database by Clerk ID
    stmt = select(User).where(User.clerk_user_id == clerk_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        logger.debug(f"Found existing user for Clerk ID: {clerk_user_id}")
        return user

    # Auto-create user on first login
    logger.info(f"Creating new user for Clerk ID: {clerk_user_id}")
    try:
        clerk_data = await ClerkAuth.get_clerk_user_data(clerk_user_id)

        # Extract email from Clerk data
        email_addresses = clerk_data.get("email_addresses", [])
        primary_email = None
        for email_obj in email_addresses:
            if email_obj.get("id") == clerk_data.get("primary_email_address_id"):
                primary_email = email_obj.get("email_address")
                break
        if not primary_email and email_addresses:
            primary_email = email_addresses[0].get("email_address")

        if not primary_email:
            logger.error(f"No email found for Clerk user: {clerk_user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User email not available"
            )

        # Create display name
        first_name = clerk_data.get("first_name", "") or ""
        last_name = clerk_data.get("last_name", "") or ""
        display_name = f"{first_name} {last_name}".strip() or primary_email.split("@")[0]

        user = User(
            clerk_user_id=clerk_user_id,
            email=primary_email,
            display_name=display_name,
            password_hash=None,  # Clerk users don't have local passwords
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Created new user: id={user.id}, email={primary_email}, clerk_id={clerk_user_id}")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create user for Clerk ID {clerk_user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )


async def get_optional_user_clerk(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise None.

    Args:
        credentials: Optional bearer token
        db: Database session

    Returns:
        User object or None if not authenticated
    """
    if not credentials:
        return None

    try:
        return await get_current_user_clerk(credentials, db)
    except HTTPException:
        return None


def verify_webhook_signature(
    payload: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str
) -> bool:
    """Verify Clerk webhook signature using Svix.

    Args:
        payload: Raw request body
        svix_id: Svix-Id header
        svix_timestamp: Svix-Timestamp header
        svix_signature: Svix-Signature header

    Returns:
        True if signature is valid, False otherwise
    """
    if not settings.clerk_webhook_secret:
        logger.error("Clerk webhook secret not configured")
        return False

    try:
        from svix.webhooks import Webhook

        wh = Webhook(settings.clerk_webhook_secret)
        wh.verify(
            payload,
            {
                "svix-id": svix_id,
                "svix-timestamp": svix_timestamp,
                "svix-signature": svix_signature,
            }
        )
        logger.debug("Webhook signature verified successfully")
        return True
    except Exception as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        return False


# ======================
# Backward Compatibility
# ======================

# For code that imports get_current_user from clerk_auth
get_current_user = get_current_user_clerk
get_optional_user = get_optional_user_clerk
