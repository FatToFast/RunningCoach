#!/usr/bin/env python
"""Check R2 migration status and storage statistics.

This script:
1. Checks migration progress
2. Calculates storage usage
3. Verifies file integrity
4. Provides detailed statistics
"""

import asyncio
import os
import sys
from typing import Dict, List
import boto3
from botocore.config import Config
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from dotenv import load_dotenv
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.activity import Activity
from app.models.user import User
from app.core.config import get_settings

load_dotenv()


class R2Checker:
    """Check R2 storage status."""

    def __init__(self):
        # R2 configuration
        account_id = os.getenv("R2_ACCOUNT_ID")
        access_key = os.getenv("R2_ACCESS_KEY_ID")
        secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
        bucket_name = os.getenv("R2_BUCKET_NAME", "fit-files")

        if not all([account_id, access_key, secret_key]):
            raise ValueError("Missing R2 configuration in environment variables")

        # Create S3 client for R2
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto"
        )
        self.bucket_name = bucket_name

    def list_objects(self, prefix: str = "") -> List[Dict]:
        """List all objects in R2 with given prefix."""
        objects = []
        paginator = self.s3_client.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if "Contents" in page:
                    objects.extend(page["Contents"])
        except Exception as e:
            print(f"Error listing R2 objects: {e}")

        return objects

    def get_storage_stats(self, user_id: Optional[int] = None) -> Dict:
        """Get storage statistics for user or all users."""
        prefix = f"users/{user_id}/" if user_id else ""
        objects = self.list_objects(prefix)

        total_size = sum(obj["Size"] for obj in objects)
        total_files = len(objects)

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "total_size_gb": total_size / (1024 * 1024 * 1024),
            "objects": objects
        }


async def check_migration_status():
    """Check overall migration status."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    print("=" * 60)
    print("R2 Migration Status Check")
    print("=" * 60)

    async with async_session() as session:
        # 1. Database statistics
        print("\n📊 Database Statistics:")
        print("-" * 40)

        # Total activities
        result = await session.execute(select(func.count(Activity.id)))
        total_activities = result.scalar()
        print(f"  Total activities: {total_activities:,}")

        # Activities with FIT files
        result = await session.execute(
            select(func.count(Activity.id)).where(Activity.has_fit_file == True)
        )
        activities_with_fits = result.scalar()
        print(f"  Activities with FIT files: {activities_with_fits:,}")

        # Activities migrated to R2
        result = await session.execute(
            select(func.count(Activity.id)).where(Activity.r2_key.isnot(None))
        )
        activities_in_r2 = result.scalar()
        print(f"  Activities in R2: {activities_in_r2:,}")

        # Migration progress
        if activities_with_fits > 0:
            progress = (activities_in_r2 / activities_with_fits) * 100
            print(f"  Migration progress: {progress:.1f}%")
            print(f"  Remaining to migrate: {activities_with_fits - activities_in_r2:,}")

        # 2. Local storage statistics
        print("\n💾 Local Storage:")
        print("-" * 40)

        fit_dir = Path(settings.fit_storage_path)
        if fit_dir.exists():
            fit_files = list(fit_dir.rglob("*.fit"))
            total_size = sum(f.stat().st_size for f in fit_files)
            print(f"  FIT directory: {fit_dir}")
            print(f"  Local FIT files: {len(fit_files):,}")
            print(f"  Total size: {total_size / (1024**2):.2f} MB")
        else:
            print(f"  FIT directory not found: {fit_dir}")

        # 3. R2 storage statistics
        print("\n☁️  R2 Storage:")
        print("-" * 40)

        try:
            checker = R2Checker()
            stats = checker.get_storage_stats()
            print(f"  Total files in R2: {stats['total_files']:,}")
            print(f"  Total size: {stats['total_size_gb']:.3f} GB")
            print(f"  Free tier usage: {(stats['total_size_gb'] / 10) * 100:.1f}%")
            print(f"  Remaining free tier: {10 - stats['total_size_gb']:.3f} GB")
        except Exception as e:
            print(f"  Error accessing R2: {e}")

        # 4. Per-user statistics
        print("\n👥 Per-User Statistics:")
        print("-" * 40)

        result = await session.execute(
            select(
                User.id,
                User.email,
                func.count(Activity.id).label("activity_count"),
                func.count(Activity.r2_key).label("r2_count")
            )
            .join(Activity, User.id == Activity.user_id)
            .group_by(User.id, User.email)
            .order_by(func.count(Activity.id).desc())
        )
        user_stats = result.all()

        print(f"  {'User':<30} {'Activities':<12} {'In R2':<12} {'Progress':<10}")
        print("  " + "-" * 64)
        for user_id, email, activity_count, r2_count in user_stats[:10]:
            progress = (r2_count / activity_count * 100) if activity_count > 0 else 0
            print(f"  {email:<30} {activity_count:<12} {r2_count:<12} {progress:>6.1f}%")

        if len(user_stats) > 10:
            print(f"  ... and {len(user_stats) - 10} more users")

        # 5. Recent migrations
        print("\n🕐 Recent Migrations:")
        print("-" * 40)

        result = await session.execute(
            select(Activity)
            .where(Activity.r2_key.isnot(None))
            .order_by(Activity.updated_at.desc())
            .limit(5)
        )
        recent_activities = result.scalars().all()

        if recent_activities:
            for activity in recent_activities:
                metadata = activity.storage_metadata or {}
                print(f"  • Activity {activity.id}: {activity.name}")
                print(f"    R2 key: {activity.r2_key}")
                if "file_size" in metadata:
                    print(f"    Size: {metadata['file_size']:,} bytes")
        else:
            print("  No recent migrations found")

    await engine.dispose()


async def verify_r2_files():
    """Verify that R2 files are accessible."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    print("\n" + "=" * 60)
    print("R2 File Verification")
    print("=" * 60)

    checker = R2Checker()

    async with async_session() as session:
        # Get sample of activities with R2 keys
        result = await session.execute(
            select(Activity)
            .where(Activity.r2_key.isnot(None))
            .limit(10)
        )
        activities = result.scalars().all()

        print(f"\nVerifying {len(activities)} sample files...")
        print("-" * 40)

        verified = 0
        failed = 0

        for activity in activities:
            try:
                # Check if object exists
                response = checker.s3_client.head_object(
                    Bucket=checker.bucket_name,
                    Key=activity.r2_key
                )
                size = response["ContentLength"]
                print(f"  ✅ Activity {activity.id}: {size:,} bytes")
                verified += 1
            except Exception as e:
                print(f"  ❌ Activity {activity.id}: {e}")
                failed += 1

        print("-" * 40)
        print(f"Verified: {verified}/{len(activities)}")
        if failed > 0:
            print(f"Failed: {failed}")

    await engine.dispose()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Check R2 migration status")
    parser.add_argument("--verify", action="store_true", help="Verify R2 files are accessible")
    args = parser.parse_args()

    asyncio.run(check_migration_status())

    if args.verify:
        asyncio.run(verify_r2_files())


if __name__ == "__main__":
    main()