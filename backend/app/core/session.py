"""Session management with Redis."""

import json
import logging
import secrets
from datetime import datetime, UTC
from typing import Any, Optional

import redis.asyncio as redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
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


async def close_redis() -> None:
    """Close Redis client connection.

    Call this during application shutdown to properly cleanup connections.
    """
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")
        finally:
            _redis_client = None


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
        "created_at": datetime.now(UTC).isoformat(),
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


# =============================================================================
# Distributed Lock (for multi-worker/multi-instance deployments)
# =============================================================================


async def acquire_lock(
    lock_name: str,
    ttl_seconds: int = 3600,
    owner: Optional[str] = None,
) -> Optional[str]:
    """Acquire a distributed lock using Redis SETNX.

    Args:
        lock_name: Name of the lock (e.g., "sync:user:123").
        ttl_seconds: Lock expiration time in seconds (default: 1 hour).
        owner: Optional owner identifier. If None, generates a random one.

    Returns:
        Lock owner token if acquired, None if lock already held.
    """
    redis_client = await get_redis()
    lock_key = f"lock:{lock_name}"
    owner = owner or secrets.token_urlsafe(16)

    # SETNX with expiration
    acquired = await redis_client.set(lock_key, owner, nx=True, ex=ttl_seconds)

    if acquired:
        logger.debug(f"Lock acquired: {lock_name} (owner={owner[:8]}...)")
        return owner
    else:
        logger.debug(f"Lock already held: {lock_name}")
        return None


async def release_lock(lock_name: str, owner: str) -> bool:
    """Release a distributed lock.

    Uses Lua script to ensure atomic check-and-delete (only owner can release).

    Args:
        lock_name: Name of the lock.
        owner: Owner token (returned from acquire_lock).

    Returns:
        True if lock was released, False if not found or owned by another.
    """
    redis_client = await get_redis()
    lock_key = f"lock:{lock_name}"

    # Lua script for atomic compare-and-delete
    lua_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    result = await redis_client.eval(lua_script, 1, lock_key, owner)

    if result == 1:
        logger.debug(f"Lock released: {lock_name}")
        return True
    else:
        logger.warning(f"Lock not released (not owner or expired): {lock_name}")
        return False


async def check_lock(lock_name: str) -> bool:
    """Check if a lock is currently held.

    Args:
        lock_name: Name of the lock.

    Returns:
        True if lock is held, False otherwise.
    """
    redis_client = await get_redis()
    lock_key = f"lock:{lock_name}"
    return await redis_client.exists(lock_key) > 0
