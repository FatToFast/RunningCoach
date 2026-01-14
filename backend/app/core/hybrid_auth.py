"""Hybrid authentication support for both session-based and Clerk JWT auth.

This module provides authentication dependencies that work with both:
1. Traditional session-based authentication (local development, existing users)
2. Clerk JWT authentication (cloud deployment)

The authentication method is determined automatically based on:
- Presence of Bearer token (Clerk JWT)
- Presence of session cookie (local session)
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.debug_utils import CloudMigrationDebug
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

# Bearer token security (for Clerk JWT)
bearer_security = HTTPBearer(auto_error=False)


async def get_current_user_hybrid(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user from either Clerk JWT or session cookie.

    This dependency tries authentication in order:
    1. Bearer token (Clerk JWT) if present
    2. Session cookie (traditional session) if present

    Args:
        request: FastAPI request object
        credentials: Optional Bearer token
        db: Database session

    Returns:
        Authenticated User object

    Raises:
        HTTPException: If no valid authentication found
    """
    # Try Clerk JWT first if Bearer token present AND Clerk is enabled
    if credentials and credentials.credentials and settings.clerk_enabled:
        try:
            from app.core.clerk_auth import ClerkAuth

            token = credentials.credentials
            payload = await ClerkAuth.verify_token(token)
            clerk_user_id = payload.get("sub")

            if clerk_user_id:
                stmt = select(User).where(User.clerk_user_id == clerk_user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()

                if user:
                    logger.debug(f"Authenticated via Clerk JWT: user_id={user.id}")
                    CloudMigrationDebug.log_hybrid_auth_flow(
                        auth_method="clerk",
                        user_id=user.id,
                        clerk_user_id=clerk_user_id,
                    )
                    return user

                # Auto-create user on first Clerk login or link to existing account
                clerk_data = await ClerkAuth.get_clerk_user_data(clerk_user_id)
                email_addresses = clerk_data.get("email_addresses", [])
                primary_email = None
                for email_obj in email_addresses:
                    if email_obj.get("id") == clerk_data.get("primary_email_address_id"):
                        primary_email = email_obj.get("email_address")
                        break
                if not primary_email and email_addresses:
                    primary_email = email_addresses[0].get("email_address")

                if primary_email:
                    # Check if user with same email already exists (account linking)
                    stmt = select(User).where(User.email == primary_email)
                    result = await db.execute(stmt)
                    existing_user = result.scalar_one_or_none()

                    if existing_user:
                        # Link Clerk ID to existing account
                        existing_user.clerk_user_id = clerk_user_id
                        await db.commit()
                        logger.info(f"Linked Clerk ID to existing user: user_id={existing_user.id}")
                        CloudMigrationDebug.log_hybrid_auth_flow(
                            auth_method="clerk",
                            user_id=existing_user.id,
                            clerk_user_id=clerk_user_id,
                        )
                        return existing_user

                    # Create new user
                    first_name = clerk_data.get("first_name", "") or ""
                    last_name = clerk_data.get("last_name", "") or ""
                    display_name = f"{first_name} {last_name}".strip() or primary_email.split("@")[0]

                    user = User(
                        clerk_user_id=clerk_user_id,
                        email=primary_email,
                        display_name=display_name,
                        password_hash=None,
                    )
                    db.add(user)
                    await db.commit()
                    await db.refresh(user)
                    logger.info(f"Created user from Clerk JWT: user_id={user.id}")
                    CloudMigrationDebug.log_hybrid_auth_flow(
                        auth_method="clerk",
                        user_id=user.id,
                        clerk_user_id=clerk_user_id,
                    )
                    return user

        except HTTPException:
            # If Clerk auth fails, try session auth
            logger.debug("Clerk JWT authentication failed, trying session auth")
        except Exception as e:
            logger.warning(f"Error during Clerk JWT authentication: {e}")

    # Try session-based authentication
    try:
        from app.core.session import get_session_user_id

        session_user_id = await get_session_user_id(request)
        if session_user_id:
            stmt = select(User).where(User.id == session_user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                logger.debug(f"Authenticated via session: user_id={user.id}")
                CloudMigrationDebug.log_hybrid_auth_flow(
                    auth_method="session",
                    user_id=user.id,
                    fallback_used=bool(credentials),
                )
                return user

    except Exception as e:
        logger.warning(f"Error during session authentication: {e}")

    # No valid authentication found
    logger.debug("No valid authentication found")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def get_optional_user_hybrid(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise None.

    Args:
        request: FastAPI request object
        credentials: Optional Bearer token
        db: Database session

    Returns:
        User object or None if not authenticated
    """
    try:
        return await get_current_user_hybrid(request, credentials, db)
    except HTTPException:
        return None


# ======================
# Convenience aliases
# ======================

# These can be used as drop-in replacements for existing auth dependencies
get_current_user = get_current_user_hybrid
get_optional_user = get_optional_user_hybrid
