#!/usr/bin/env python3
"""
Migrate FIT files from filesystem to database storage.

This script:
1. Finds all FIT files in the filesystem
2. Compresses and stores them in the database
3. Optionally removes the original files
4. Provides statistics on storage savings
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_context
from app.core.config import settings
from app.models.garmin import GarminRawFile
from app.models.activity import Activity
from app.services.fit_storage_service import FitStorageService


async def migrate_all_fit_files(
    delete_originals: bool = False,
    batch_size: int = 10
) -> None:
    """Migrate all FIT files from filesystem to database.

    Args:
        delete_originals: Whether to delete original files after migration
        batch_size: Number of files to process at once
    """
    async with get_db_context() as db:
        storage_service = FitStorageService()

        # Count total files to migrate
        total_query = select(func.count(GarminRawFile.id)).where(
            GarminRawFile.file_path.isnot(None),
            GarminRawFile.file_content.is_(None)
        )
        total_result = await db.execute(total_query)
        total_count = total_result.scalar() or 0

        if total_count == 0:
            print("No files to migrate!")
            return

        print(f"Found {total_count} FIT files to migrate")

        # Process in batches
        migrated = 0
        failed = 0
        total_original_size = 0
        total_compressed_size = 0

        offset = 0
        while offset < total_count:
            # Get batch of files
            query = (
                select(GarminRawFile)
                .where(
                    GarminRawFile.file_path.isnot(None),
                    GarminRawFile.file_content.is_(None)
                )
                .limit(batch_size)
                .offset(offset)
            )
            result = await db.execute(query)
            garmin_files = result.scalars().all()

            if not garmin_files:
                break

            # Process each file in batch
            for garmin_file in garmin_files:
                file_path = Path(garmin_file.file_path)

                if not file_path.exists():
                    print(f"⚠️ File not found: {file_path}")
                    failed += 1
                    continue

                try:
                    # Read original file
                    original_size = file_path.stat().st_size
                    file_content = file_path.read_bytes()

                    # Store to DB
                    await storage_service.store_fit_file_to_db(
                        db, garmin_file, file_content, compression="gzip"
                    )

                    # Track sizes
                    total_original_size += original_size
                    if garmin_file.file_content:
                        total_compressed_size += len(garmin_file.file_content)

                    # Delete original if requested
                    if delete_originals:
                        file_path.unlink()
                        print(f"✓ Migrated and deleted: {file_path.name}")
                    else:
                        print(f"✓ Migrated: {file_path.name}")

                    migrated += 1

                except Exception as e:
                    print(f"✗ Failed to migrate {file_path}: {e}")
                    failed += 1
                    await db.rollback()
                    continue

            offset += batch_size

            # Progress update
            print(f"Progress: {migrated + failed}/{total_count} files processed")

        # Final statistics
        print("\n" + "="*50)
        print("Migration Complete!")
        print(f"✓ Successfully migrated: {migrated} files")
        if failed > 0:
            print(f"✗ Failed: {failed} files")

        if total_original_size > 0:
            compression_ratio = (1 - total_compressed_size / total_original_size) * 100
            print(f"\nStorage Statistics:")
            print(f"  Original size: {total_original_size / 1024 / 1024:.2f} MB")
            print(f"  Compressed size: {total_compressed_size / 1024 / 1024:.2f} MB")
            print(f"  Compression ratio: {compression_ratio:.1f}% saved")

        # Also migrate Activity table fit_file_path references
        print("\nUpdating Activity table references...")
        activity_query = (
            select(Activity)
            .where(Activity.fit_file_path.isnot(None))
        )
        result = await db.execute(activity_query)
        activities = result.scalars().all()

        for activity in activities:
            # Find corresponding GarminRawFile
            garmin_query = (
                select(GarminRawFile)
                .where(GarminRawFile.activity_id == activity.id)
                .limit(1)
            )
            garmin_result = await db.execute(garmin_query)
            garmin_file = garmin_result.scalar_one_or_none()

            if garmin_file and garmin_file.file_content:
                # Copy compressed content to activity for faster access
                activity.fit_file_content = garmin_file.file_content
                activity.fit_file_size = garmin_file.file_size

                # Clear file path since it's now in DB
                if delete_originals:
                    activity.fit_file_path = None

        await db.commit()
        print("✓ Activity table updated")


async def verify_migration() -> None:
    """Verify that migration was successful."""
    async with get_db_context() as db:
        storage_service = FitStorageService()

        # Get a sample of migrated files
        query = (
            select(GarminRawFile)
            .where(GarminRawFile.file_content.isnot(None))
            .limit(5)
        )
        result = await db.execute(query)
        garmin_files = result.scalars().all()

        print(f"\nVerifying {len(garmin_files)} migrated files...")

        for garmin_file in garmin_files:
            try:
                # Retrieve and decompress
                file_content = await storage_service.retrieve_fit_file_from_db(
                    db, garmin_file
                )

                if file_content:
                    print(f"✓ File ID {garmin_file.id}: "
                          f"{garmin_file.file_size} bytes, "
                          f"hash verified: {garmin_file.file_hash[:8]}...")
                else:
                    print(f"✗ File ID {garmin_file.id}: Failed to retrieve")

            except Exception as e:
                print(f"✗ File ID {garmin_file.id}: Error - {e}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate FIT files to database storage"
    )
    parser.add_argument(
        "--delete-originals",
        action="store_true",
        help="Delete original files after successful migration"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Only verify existing migrations"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of files to process at once (default: 10)"
    )

    args = parser.parse_args()

    if args.verify:
        await verify_migration()
    else:
        if args.delete_originals:
            response = input("⚠️  This will DELETE original files after migration. "
                           "Are you sure? (yes/no): ")
            if response.lower() != "yes":
                print("Aborted.")
                return

        await migrate_all_fit_files(
            delete_originals=args.delete_originals,
            batch_size=args.batch_size
        )


if __name__ == "__main__":
    asyncio.run(main())