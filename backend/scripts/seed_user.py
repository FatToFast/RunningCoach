#!/usr/bin/env python3
"""Seed script to create initial user accounts.

FR-000: 로컬 로그인 - 계정 생성은 초기 seed/스크립트로만 진행 (셀프 가입 없음)

Usage:
    # Interactive mode
    python scripts/seed_user.py

    # Command line mode
    python scripts/seed_user.py --email user@example.com --password secret123 --name "User Name"

    # From environment variables
    SEED_EMAIL=user@example.com SEED_PASSWORD=secret123 python scripts/seed_user.py
"""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from argon2 import PasswordHasher
from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.user import User


ph = PasswordHasher()


async def create_user(
    email: str,
    password: str,
    display_name: str | None = None,
    timezone: str = "Asia/Seoul",
) -> User:
    """Create a new user in the database.

    Args:
        email: User email address.
        password: Plain text password (will be hashed).
        display_name: Optional display name.
        timezone: User timezone (default: Asia/Seoul).

    Returns:
        Created User object.

    Raises:
        ValueError: If user with email already exists.
    """
    async with async_session_maker() as session:
        # Check if user exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(f"User with email '{email}' already exists")

        # Hash password with Argon2
        password_hash = ph.hash(password)

        # Create user
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            timezone=timezone,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        return user


async def list_users() -> list[User]:
    """List all existing users.

    Returns:
        List of User objects.
    """
    async with async_session_maker() as session:
        result = await session.execute(select(User))
        return list(result.scalars().all())


def get_password_interactive() -> str:
    """Get password interactively with confirmation.

    Returns:
        Confirmed password.

    Raises:
        ValueError: If passwords don't match.
    """
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        raise ValueError("Passwords do not match")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    return password


async def main() -> None:
    """Main entry point for the seed script."""
    parser = argparse.ArgumentParser(
        description="Create initial user accounts for RunningCoach"
    )
    parser.add_argument(
        "--email",
        help="User email address",
        default=os.environ.get("SEED_EMAIL"),
    )
    parser.add_argument(
        "--password",
        help="User password (or use SEED_PASSWORD env var)",
        default=os.environ.get("SEED_PASSWORD"),
    )
    parser.add_argument(
        "--name",
        help="Display name",
        default=os.environ.get("SEED_NAME"),
    )
    parser.add_argument(
        "--timezone",
        help="User timezone",
        default=os.environ.get("SEED_TIMEZONE", "Asia/Seoul"),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing users",
    )

    args = parser.parse_args()

    # List users if requested
    if args.list:
        print("\nExisting users:")
        print("-" * 50)
        users = await list_users()
        if not users:
            print("No users found")
        else:
            for user in users:
                print(f"  ID: {user.id}")
                print(f"  Email: {user.email}")
                print(f"  Name: {user.display_name or '(not set)'}")
                print(f"  Timezone: {user.timezone}")
                print(f"  Created: {user.created_at}")
                print("-" * 50)
        return

    # Interactive mode if email not provided
    if not args.email:
        print("\n=== RunningCoach User Creation ===\n")
        args.email = input("Email: ").strip()
        if not args.email:
            print("Error: Email is required")
            sys.exit(1)

    # Interactive mode if password not provided
    if not args.password:
        try:
            args.password = get_password_interactive()
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    # Interactive mode for name if not provided
    if args.name is None:
        args.name = input("Display name (optional): ").strip() or None

    # Create user
    try:
        user = await create_user(
            email=args.email,
            password=args.password,
            display_name=args.name,
            timezone=args.timezone,
        )
        print(f"\n✅ User created successfully!")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Name: {user.display_name or '(not set)'}")
        print(f"   Timezone: {user.timezone}")
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Database error: {e}")
        print("\nMake sure the database is running and migrations are applied.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
