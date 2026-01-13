#!/usr/bin/env python
"""Migrate FIT files from local storage to Cloudflare R2.

This script:
1. Scans the local FIT file directory
2. Uploads each file to R2 with proper key structure
3. Updates the database with R2 keys
4. Optionally deletes local files after successful upload
"""

import asyncio
import gzip
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import boto3
from botocore.config import Config
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.activity import Activity
from app.core.config import get_settings

load_dotenv()


class R2Migrator:
    """Handle FIT file migration to R2."""

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

    def compress_data(self, data: bytes) -> bytes:
        """Compress data using gzip."""
        return gzip.compress(data, compresslevel=9)

    def generate_key(self, user_id: int, activity_id: int) -> str:
        """Generate S3 key for FIT file."""
        return f"users/{user_id}/activities/{activity_id}/activity.fit.gz"

    async def upload_to_r2(
        self,
        file_path: Path,
        user_id: int,
        activity_id: int
    ) -> Tuple[bool, Optional[str]]:
        """Upload a FIT file to R2."""
        try:
            # Read and compress file
            with open(file_path, "rb") as f:
                fit_data = f.read()

            compressed_data = self.compress_data(fit_data)
            key = self.generate_key(user_id, activity_id)

            # Upload to R2
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=compressed_data,
                ContentType="application/octet-stream",
                ContentEncoding="gzip",
                Metadata={
                    "original_size": str(len(fit_data)),
                    "compressed_size": str(len(compressed_data)),
                    "compression_ratio": f"{len(compressed_data) / len(fit_data):.2%}"
                }
            )

            return True, key

        except Exception as e:
            print(f"    Error uploading to R2: {e}")
            return False, None


async def migrate_fit_files(
    delete_after_upload: bool = False,
    dry_run: bool = False,
    limit: Optional[int] = None
):
    """Migrate all FIT files to R2."""
    settings = get_settings()

    # FIT file directory
    fit_dir = Path(settings.fit_storage_path)
    if not fit_dir.exists():
        print(f"FIT directory not found: {fit_dir}")
        return

    # Database connection
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # R2 migrator
    migrator = R2Migrator() if not dry_run else None

    print(f"Starting FIT file migration to R2")
    print(f"  Source directory: {fit_dir}")
    print(f"  Delete after upload: {delete_after_upload}")
    print(f"  Dry run: {dry_run}")
    if limit:
        print(f"  Limit: {limit} files")
    print("-" * 50)

    # Find all FIT files
    fit_files = list(fit_dir.rglob("*.fit"))
    print(f"Found {len(fit_files)} FIT files")

    if limit:
        fit_files = fit_files[:limit]
        print(f"Processing first {limit} files")

    uploaded_count = 0
    skipped_count = 0
    failed_count = 0

    async with async_session() as session:
        for i, file_path in enumerate(fit_files, 1):
            # Extract user_id and activity_id from path
            # Expected format: data/fit_files/{user_id}/{activity_id}.fit
            parts = file_path.parts
            try:
                user_id = int(parts[-2])
                activity_id = int(file_path.stem)
            except (ValueError, IndexError):
                print(f"\n[{i}/{len(fit_files)}] Skipping invalid path: {file_path}")
                skipped_count += 1
                continue

            print(f"\n[{i}/{len(fit_files)}] Processing: user={user_id}, activity={activity_id}")

            # Check if activity exists and already has R2 key
            result = await session.execute(
                select(Activity).where(Activity.id == activity_id)
            )
            activity = result.scalar_one_or_none()

            if not activity:
                print(f"  Activity not found in database")
                skipped_count += 1
                continue

            if activity.r2_key:
                print(f"  Already uploaded (R2 key: {activity.r2_key})")
                skipped_count += 1
                continue

            # Get file size
            file_size = file_path.stat().st_size
            print(f"  File size: {file_size:,} bytes")

            if dry_run:
                print(f"  [DRY RUN] Would upload to R2")
                uploaded_count += 1
                continue

            # Upload to R2
            success, r2_key = await migrator.upload_to_r2(file_path, user_id, activity_id)

            if success:
                # Update database
                await session.execute(
                    update(Activity)
                    .where(Activity.id == activity_id)
                    .values(
                        r2_key=r2_key,
                        storage_provider="r2",
                        storage_metadata={
                            "migrated": True,
                            "original_path": str(file_path),
                            "file_size": file_size
                        }
                    )
                )
                await session.commit()
                print(f"  ✅ Uploaded to R2: {r2_key}")
                uploaded_count += 1

                # Delete local file if requested
                if delete_after_upload:
                    file_path.unlink()
                    print(f"  🗑️  Deleted local file")
            else:
                print(f"  ❌ Failed to upload")
                failed_count += 1

    print("\n" + "=" * 50)
    print("Migration Summary:")
    print(f"  Uploaded: {uploaded_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Total processed: {len(fit_files)}")

    await engine.dispose()


async def verify_migration():
    """Verify R2 migration status."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Count activities with FIT files
        result = await session.execute(
            select(Activity).where(Activity.has_fit_file == True)
        )
        activities_with_fits = result.scalars().all()

        # Count activities with R2 keys
        result = await session.execute(
            select(Activity).where(Activity.r2_key.isnot(None))
        )
        activities_with_r2 = result.scalars().all()

        print("\nMigration Status:")
        print(f"  Activities with FIT files: {len(activities_with_fits)}")
        print(f"  Activities migrated to R2: {len(activities_with_r2)}")
        print(f"  Remaining to migrate: {len(activities_with_fits) - len(activities_with_r2)}")

        # List unmigrated activities
        unmigrated = [a for a in activities_with_fits if not a.r2_key]
        if unmigrated[:10]:
            print(f"\n  First 10 unmigrated activities:")
            for activity in unmigrated[:10]:
                print(f"    - Activity {activity.id}: {activity.name}")

    await engine.dispose()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate FIT files to R2 storage")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without making changes")
    parser.add_argument("--delete", action="store_true", help="Delete local files after successful upload")
    parser.add_argument("--limit", type=int, help="Limit number of files to process")
    parser.add_argument("--verify", action="store_true", help="Verify migration status")
    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify_migration())
    else:
        asyncio.run(migrate_fit_files(
            delete_after_upload=args.delete,
            dry_run=args.dry_run,
            limit=args.limit
        ))


if __name__ == "__main__":
    main()