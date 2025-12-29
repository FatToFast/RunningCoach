"""Session management with Redis."""

import secrets
from datetime import datetime, timedelta
from typing import Any, Optional
import json

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()

# Redis client (initialized lazily)
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


def generate_session_id() -> str:
    """Generate a secure random session ID."""
    return secrets.token_urlsafe(32)


async def create_session(user_id: int, user_data: dict[str, Any]) -> str:
    """Create a new session in Redis.

    Args:
        user_id: User ID to store in session.
        user_data: Additional user data to store.

    Returns:
        Session ID.
    """
    redis_client = await get_redis()
    session_id = generate_session_id()

    session_data = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        **user_data,
    }

    ttl = settings.session_ttl_seconds
    await redis_client.setex(
        f"session:{session_id}",
        ttl,
        json.dumps(session_data),
    )

    return session_id


async def get_session(session_id: str) -> Optional[dict[str, Any]]:
    """Get session data from Redis.

    Args:
        session_id: Session ID.

    Returns:
        Session data or None if not found/expired.
    """
    redis_client = await get_redis()
    data = await redis_client.get(f"session:{session_id}")

    if data is None:
        return None

    return json.loads(data)


async def delete_session(session_id: str) -> bool:
    """Delete a session from Redis.

    Args:
        session_id: Session ID to delete.

    Returns:
        True if session was deleted, False otherwise.
    """
    redis_client = await get_redis()
    result = await redis_client.delete(f"session:{session_id}")
    return result > 0


async def refresh_session(session_id: str) -> bool:
    """Refresh session TTL.

    Args:
        session_id: Session ID to refresh.

    Returns:
        True if session was refreshed, False if not found.
    """
    redis_client = await get_redis()
    ttl = settings.session_ttl_seconds
    result = await redis_client.expire(f"session:{session_id}", ttl)
    return result
