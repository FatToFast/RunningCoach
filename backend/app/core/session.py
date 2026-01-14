"""Session management with Redis.

Provides graceful fallback when Redis is unavailable:
- Lock functions return safe defaults (no lock held)
- Session functions return None (use JWT auth instead)
"""

import json
import logging
import secrets
from datetime import datetime, UTC
from typing import Any, Optional

import redis.asyncio as redis
from redis.exceptions import ConnectionError, RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis client (initialized lazily)
_redis_client: Optional[redis.Redis] = None
_redis_available: Optional[bool] = None  # Cache availability check


async def get_redis() -> Optional[redis.Redis]:
    """Get Redis client instance.

    Returns:
        Redis client or None if unavailable.
    """
    global _redis_client, _redis_available

    # If we already know Redis is unavailable, return None immediately
    if _redis_available is False:
        return None

    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    # Test connection on first call
    if _redis_available is None:
        try:
            await _redis_client.ping()
            _redis_available = True
            logger.info("Redis connection established")
        except (ConnectionError, RedisError, OSError) as e:
            logger.warning(f"Redis unavailable: {e}. Session/lock features disabled.")
            _redis_available = False
            return None

    return _redis_client


async def close_redis() -> None:
    """Close Redis client connection.

    Call this during application shutdown to properly cleanup connections.
    """
    global _redis_client, _redis_available
    if _redis_client is not None:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")
        finally:
            _redis_client = None
            _redis_available = None


def generate_session_id() -> str:
    """Generate a secure random session ID."""
    return secrets.token_urlsafe(32)


async def create_session(user_id: int, user_data: dict[str, Any]) -> Optional[str]:
    """Create a new session in Redis.

    Args:
        user_id: User ID to store in session.
        user_data: Additional user data to store.

    Returns:
        Session ID, or None if Redis unavailable.
    """
    redis_client = await get_redis()
    if redis_client is None:
        logger.warning("Cannot create session: Redis unavailable")
        return None

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
        Session data or None if not found/expired/Redis unavailable.
    """
    redis_client = await get_redis()
    if redis_client is None:
        return None

    data = await redis_client.get(f"session:{session_id}")

    if data is None:
        return None

    return json.loads(data)


async def get_session_user_id(request: Any) -> Optional[int]:
    """Get user ID from session cookie.

    Args:
        request: FastAPI request object.

    Returns:
        User ID if valid session exists, None otherwise.
    """
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None

    session_data = await get_session(session_id)
    if not session_data:
        return None

    return session_data.get("user_id")


async def delete_session(session_id: str) -> bool:
    """Delete a session from Redis.

    Args:
        session_id: Session ID to delete.

    Returns:
        True if session was deleted, False if Redis unavailable.
    """
    redis_client = await get_redis()
    if redis_client is None:
        return False

    result = await redis_client.delete(f"session:{session_id}")
    return result > 0


async def refresh_session(session_id: str) -> bool:
    """Refresh session TTL.

    Args:
        session_id: Session ID to refresh.

    Returns:
        True if session was refreshed, False if not found/Redis unavailable.
    """
    redis_client = await get_redis()
    if redis_client is None:
        return False

    ttl = settings.session_ttl_seconds
    result = await redis_client.expire(f"session:{session_id}", ttl)
    return result


# =============================================================================
# Distributed Lock (for multi-worker/multi-instance deployments)
# Note: When Redis is unavailable, locks are effectively disabled.
# This allows the app to function but without distributed lock protection.
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
        Lock owner token if acquired, None if lock already held or Redis unavailable.
    """
    redis_client = await get_redis()
    if redis_client is None:
        # Redis unavailable - allow operation but log warning
        logger.warning(f"Lock disabled (no Redis): {lock_name}")
        return secrets.token_urlsafe(16)  # Return fake owner to allow operation

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
    if redis_client is None:
        return True  # No-op when Redis unavailable

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
        True if lock is held, False otherwise (including Redis unavailable).
    """
    redis_client = await get_redis()
    if redis_client is None:
        return False  # No lock when Redis unavailable

    lock_key = f"lock:{lock_name}"
    return await redis_client.exists(lock_key) > 0


async def extend_lock(lock_name: str, owner: str, ttl_seconds: int) -> bool:
    """Extend a distributed lock's TTL.

    Uses Lua script to ensure atomic check-and-extend (only owner can extend).

    Args:
        lock_name: Name of the lock.
        owner: Owner token (returned from acquire_lock).
        ttl_seconds: New TTL in seconds.

    Returns:
        True if lock was extended, False if not found or owned by another.
    """
    redis_client = await get_redis()
    if redis_client is None:
        return True  # No-op when Redis unavailable

    lock_key = f"lock:{lock_name}"

    # Lua script for atomic compare-and-expire
    lua_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("expire", KEYS[1], ARGV[2])
    else
        return 0
    end
    """

    result = await redis_client.eval(lua_script, 1, lock_key, owner, ttl_seconds)

    if result == 1:
        logger.debug(f"Lock extended: {lock_name} (new TTL={ttl_seconds}s)")
        return True
    else:
        logger.warning(f"Lock not extended (not owner or expired): {lock_name}")
        return False
