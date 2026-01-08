#!/usr/bin/env python3
"""Cleanup FIT files that have already been parsed and stored in the database.

This script safely deletes FIT files that have been successfully parsed,
saving disk space while preserving all data in the database.

Safety checks:
- Only deletes files with sufficient ActivitySample records (default: 10)
- Dry-run mode to preview changes before deletion
- Preserves fit_file_hash for verification if re-download is ever needed

Usage:
    # Preview what would be deleted (dry-run)
    python scripts/cleanup_fit_files.py --dry-run

    # Actually delete files
    python scripts/cleanup_fit_files.py

    # Custom minimum sample count
    python scripts/cleanup_fit_files.py --min-samples 20
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.activity import Activity, ActivitySample
from app.models.garmin import GarminRawFile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def cleanup_fit_files(
    dry_run: bool = True,
    min_samples: int = 10,
) -> dict:
    """Clean up FIT files that have been successfully parsed.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting.
        min_samples: Minimum ActivitySample records required before deleting FIT file.

    Returns:
        Summary dict with counts and sizes.
    """
    settings = get_settings()

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    summary = {
        "total_files": 0,
        "files_to_delete": 0,
        "files_preserved": 0,
        "bytes_to_free": 0,
        "bytes_freed": 0,
        "errors": 0,
    }

    async with async_session() as session:
        # Get all activities with FIT files
        result = await session.execute(
            select(Activity).where(
                Activity.fit_file_path != None,
                Activity.has_fit_file == True,
            )
        )
        activities = result.scalars().all()

        logger.info(f"Found {len(activities)} activities with FIT files")
        summary["total_files"] = len(activities)

        for activity in activities:
            file_path = activity.fit_file_path

            # Skip if file doesn't exist
            if not file_path or not os.path.exists(file_path):
                logger.debug(f"File not found, skipping: {file_path}")
                continue

            # Count samples for this activity
            sample_count_result = await session.execute(
                select(func.count(ActivitySample.id)).where(
                    ActivitySample.activity_id == activity.id
                )
            )
            sample_count = sample_count_result.scalar() or 0

            file_size = os.path.getsize(file_path)

            if sample_count >= min_samples:
                summary["files_to_delete"] += 1
                summary["bytes_to_free"] += file_size

                if dry_run:
                    logger.info(
                        f"[DRY-RUN] Would delete: {file_path} "
                        f"(activity={activity.garmin_id}, samples={sample_count}, size={file_size/1024:.1f}KB)"
                    )
                else:
                    try:
                        os.remove(file_path)
                        summary["bytes_freed"] += file_size

                        # Update activity record
                        activity.fit_file_path = None

                        # Update GarminRawFile record
                        raw_file_result = await session.execute(
                            select(GarminRawFile).where(
                                GarminRawFile.activity_id == activity.id
                            )
                        )
                        raw_file = raw_file_result.scalar_one_or_none()
                        if raw_file:
                            raw_file.file_path = None

                        logger.info(
                            f"Deleted: {file_path} "
                            f"(activity={activity.garmin_id}, samples={sample_count}, size={file_size/1024:.1f}KB)"
                        )
                    except Exception as e:
                        summary["errors"] += 1
                        logger.error(f"Failed to delete {file_path}: {e}")
            else:
                summary["files_preserved"] += 1
                logger.warning(
                    f"Preserved (insufficient samples): {file_path} "
                    f"(activity={activity.garmin_id}, samples={sample_count}, min_required={min_samples})"
                )

        if not dry_run:
            await session.commit()

            # Clean up empty user directories
            fit_storage = Path(settings.fit_storage_path_absolute)
            if fit_storage.exists():
                for user_dir in fit_storage.iterdir():
                    if user_dir.is_dir() and not any(user_dir.iterdir()):
                        user_dir.rmdir()
                        logger.info(f"Removed empty directory: {user_dir}")

    await engine.dispose()
    return summary


def format_size(bytes_count: int) -> str:
    """Format bytes as human-readable size."""
    if bytes_count >= 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    elif bytes_count >= 1024:
        return f"{bytes_count / 1024:.1f} KB"
    else:
        return f"{bytes_count} bytes"


def main():
    parser = argparse.ArgumentParser(
        description="Clean up FIT files that have been parsed and stored in the database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=10,
        help="Minimum ActivitySample records required before deleting (default: 10)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("FIT File Cleanup Script")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("MODE: Dry-run (no files will be deleted)")
    else:
        logger.info("MODE: LIVE (files will be deleted)")

    logger.info(f"Minimum samples required: {args.min_samples}")
    logger.info("-" * 60)

    summary = asyncio.run(cleanup_fit_files(dry_run=args.dry_run, min_samples=args.min_samples))

    logger.info("-" * 60)
    logger.info("Summary:")
    logger.info(f"  Total FIT files found: {summary['total_files']}")
    logger.info(f"  Files to delete: {summary['files_to_delete']}")
    logger.info(f"  Files preserved (low samples): {summary['files_preserved']}")
    logger.info(f"  Errors: {summary['errors']}")

    if args.dry_run:
        logger.info(f"  Space that would be freed: {format_size(summary['bytes_to_free'])}")
        logger.info("")
        logger.info("To actually delete files, run without --dry-run flag:")
        logger.info("  python scripts/cleanup_fit_files.py")
    else:
        logger.info(f"  Space freed: {format_size(summary['bytes_freed'])}")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
