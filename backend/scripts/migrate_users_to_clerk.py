#!/usr/bin/env python
"""Migrate existing users to Clerk authentication.

This script:
1. Fetches all existing users from the database
2. Creates corresponding users in Clerk
3. Updates the database with Clerk user IDs
4. Optionally disables local password auth
"""

import asyncio
import os
import sys
from typing import List, Optional
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.user import User
from app.core.config import get_settings

load_dotenv()


class ClerkMigrator:
    """Handle user migration to Clerk."""

    def __init__(self, clerk_secret_key: str):
        self.clerk_secret_key = clerk_secret_key
        self.base_url = "https://api.clerk.com/v1"
        self.headers = {
            "Authorization": f"Bearer {clerk_secret_key}",
            "Content-Type": "application/json"
        }

    async def create_clerk_user(self, email: str, user_id: int) -> Optional[str]:
        """Create a user in Clerk and return the Clerk user ID."""
        async with httpx.AsyncClient() as client:
            try:
                # Check if user already exists
                response = await client.get(
                    f"{self.base_url}/users",
                    headers=self.headers,
                    params={"email_address": [email]}
                )

                if response.status_code == 200:
                    users = response.json()
                    if users:
                        clerk_user_id = users[0]["id"]
                        print(f"  User already exists in Clerk: {email} -> {clerk_user_id}")
                        return clerk_user_id

                # Create new user
                response = await client.post(
                    f"{self.base_url}/users",
                    headers=self.headers,
                    json={
                        "email_address": [email],
                        "skip_password_requirement": True,
                        "public_metadata": {
                            "legacy_user_id": user_id,
                            "migrated": True
                        }
                    }
                )

                if response.status_code == 200:
                    clerk_user = response.json()
                    clerk_user_id = clerk_user["id"]
                    print(f"  Created in Clerk: {email} -> {clerk_user_id}")
                    return clerk_user_id
                else:
                    print(f"  Failed to create user {email}: {response.status_code}")
                    print(f"    Response: {response.text}")
                    return None

            except Exception as e:
                print(f"  Error creating Clerk user for {email}: {e}")
                return None


async def migrate_users(dry_run: bool = False):
    """Migrate all existing users to Clerk."""
    settings = get_settings()

    # Get Clerk secret key
    clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
    if not clerk_secret_key:
        print("ERROR: CLERK_SECRET_KEY not found in environment variables")
        return

    # Database connection
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    migrator = ClerkMigrator(clerk_secret_key)

    print(f"Starting user migration to Clerk (dry_run={dry_run})")
    print("-" * 50)

    async with async_session() as session:
        # Fetch all users
        result = await session.execute(
            select(User).order_by(User.id)
        )
        users = result.scalars().all()

        print(f"Found {len(users)} users to migrate")
        print("-" * 50)

        migrated_count = 0
        skipped_count = 0
        failed_count = 0

        for user in users:
            print(f"\nProcessing user {user.id}: {user.email}")

            # Skip if already has Clerk ID
            if user.clerk_user_id:
                print(f"  Already migrated (Clerk ID: {user.clerk_user_id})")
                skipped_count += 1
                continue

            if dry_run:
                print(f"  [DRY RUN] Would migrate user {user.email}")
                migrated_count += 1
                continue

            # Create user in Clerk
            clerk_user_id = await migrator.create_clerk_user(user.email, user.id)

            if clerk_user_id:
                # Update database with Clerk ID
                await session.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(clerk_user_id=clerk_user_id)
                )
                await session.commit()
                print(f"  Updated database with Clerk ID")
                migrated_count += 1
            else:
                print(f"  Failed to migrate user")
                failed_count += 1

    print("\n" + "=" * 50)
    print("Migration Summary:")
    print(f"  Migrated: {migrated_count}")
    print(f"  Skipped (already migrated): {skipped_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Total: {len(users)}")

    await engine.dispose()


async def verify_migration():
    """Verify that all users have been migrated."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Count users without Clerk ID
        result = await session.execute(
            select(User).where(User.clerk_user_id.is_(None))
        )
        users_without_clerk = result.scalars().all()

        if users_without_clerk:
            print(f"\nWARNING: {len(users_without_clerk)} users still need migration:")
            for user in users_without_clerk:
                print(f"  - {user.email} (ID: {user.id})")
        else:
            print("\n✅ All users have been successfully migrated to Clerk!")

    await engine.dispose()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate users to Clerk authentication")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without making changes")
    parser.add_argument("--verify", action="store_true", help="Verify migration status")
    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify_migration())
    else:
        asyncio.run(migrate_users(dry_run=args.dry_run))


if __name__ == "__main__":
    main()