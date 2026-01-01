"""Security utilities for authentication.

bcrypt operations are CPU-intensive and block the event loop.
This module provides both sync and async versions:
- verify_password / get_password_hash: Sync versions for use in sync contexts
- verify_password_async / get_password_hash_async: Async versions that run in threadpool
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import bcrypt

from app.core.config import get_settings

settings = get_settings()

# Dedicated threadpool for CPU-intensive password operations
_password_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bcrypt_")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password (sync).

    WARNING: This blocks the event loop. Use verify_password_async in async contexts.

    Args:
        plain_password: Plain text password.
        hashed_password: Hashed password to compare against.

    Returns:
        True if password matches, False otherwise.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password (async).

    Runs bcrypt in a threadpool to avoid blocking the event loop.

    Args:
        plain_password: Plain text password.
        hashed_password: Hashed password to compare against.

    Returns:
        True if password matches, False otherwise.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _password_executor,
        verify_password,
        plain_password,
        hashed_password,
    )


def get_password_hash(password: str) -> str:
    """Hash a password (sync).

    WARNING: This blocks the event loop. Use get_password_hash_async in async contexts.

    Args:
        password: Plain text password.

    Returns:
        Hashed password.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def get_password_hash_async(password: str) -> str:
    """Hash a password (async).

    Runs bcrypt in a threadpool to avoid blocking the event loop.

    Args:
        password: Plain text password.

    Returns:
        Hashed password.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _password_executor,
        get_password_hash,
        password,
    )
