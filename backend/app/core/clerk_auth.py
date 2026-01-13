"""Clerk authentication middleware for JWT verification."""

import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User

# Clerk configuration
CLERK_PUBLISHABLE_KEY = os.getenv("CLERK_PUBLISHABLE_KEY", "")
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY", "")
CLERK_JWKS_URL = f"https://{CLERK_PUBLISHABLE_KEY.split('_')[2]}.clerk.accounts.dev/.well-known/jwks.json"

# Security scheme
security = HTTPBearer()

# JWKS client for token verification
jwks_client = PyJWKClient(CLERK_JWKS_URL) if CLERK_PUBLISHABLE_KEY else None


class ClerkAuth:
    """Clerk authentication handler."""

    @staticmethod
    async def verify_token(token: str) -> dict:
        """Verify Clerk JWT token.

        Args:
            token: JWT token from Authorization header

        Returns:
            Decoded JWT payload

        Raises:
            HTTPException: If token is invalid
        """
        if not jwks_client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk not configured"
            )

        try:
            # Get signing key from JWKS
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            # Verify and decode token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False}  # Clerk doesn't always set audience
            )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )

    @staticmethod
    async def get_clerk_user(token: str) -> dict:
        """Get user data from Clerk API.

        Args:
            token: JWT token

        Returns:
            Clerk user data
        """
        payload = await ClerkAuth.verify_token(token)
        clerk_user_id = payload.get("sub")

        if not clerk_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Optional: Fetch additional user data from Clerk API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.clerk.com/v1/users/{clerk_user_id}",
                headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to fetch user data"
                )

            return response.json()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user from Clerk JWT token.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        User object from database

    Raises:
        HTTPException: If user not found or token invalid
    """
    token = credentials.credentials

    # Verify token and get payload
    payload = await ClerkAuth.verify_token(token)
    clerk_user_id = payload.get("sub")

    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # Find user in database by Clerk ID
    stmt = select(User).where(User.clerk_user_id == clerk_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create user on first login
        clerk_data = await ClerkAuth.get_clerk_user(token)

        user = User(
            clerk_user_id=clerk_user_id,
            email=clerk_data.get("email_addresses", [{}])[0].get("email_address"),
            display_name=f"{clerk_data.get('first_name', '')} {clerk_data.get('last_name', '')}".strip(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise None.

    Args:
        credentials: Optional bearer token
        db: Database session

    Returns:
        User object or None
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


# Webhook signature verification
def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Clerk webhook signature.

    Args:
        payload: Raw request body
        signature: Signature from Svix-Signature header

    Returns:
        True if signature is valid
    """
    from svix import Webhook

    webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return False

    wh = Webhook(webhook_secret)

    try:
        wh.verify(payload, {"svix-signature": signature})
        return True
    except Exception:
        return False