"""ARQ worker for Strava upload processing.

This module defines the ARQ worker configuration and tasks for processing
Strava upload jobs asynchronously.

Usage:
    # Start the worker
    arq app.workers.strava_worker.WorkerSettings

    # Or with environment-specific settings
    REDIS_URL=redis://localhost:6379/0 arq app.workers.strava_worker.WorkerSettings
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.strava import StravaUploadJob, StravaUploadStatus
from app.services.strava_upload import StravaUploadService

settings = get_settings()
logger = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    """Parse Redis URL into RedisSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


async def get_db_session() -> AsyncSession:
    """Create a database session for worker tasks."""
    engine = create_async_engine(settings.database_url, echo=settings.database_echo)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


async def process_strava_upload(ctx: dict, job_id: int) -> dict[str, Any]:
    """Process a single Strava upload job.

    Args:
        ctx: ARQ context (contains Redis connection).
        job_id: ID of the StravaUploadJob to process.

    Returns:
        Result dictionary with job status.
    """
    logger.info(f"Processing Strava upload job {job_id}")

    async with await get_db_session() as db:
        try:
            # Fetch job
            result = await db.execute(
                select(StravaUploadJob).where(StravaUploadJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                logger.warning(f"Job {job_id} not found")
                return {"success": False, "error": "Job not found"}

            if job.status not in (
                StravaUploadStatus.QUEUED.value,
                StravaUploadStatus.POLLING.value,
            ):
                logger.info(f"Job {job_id} already processed (status: {job.status})")
                return {"success": True, "status": job.status}

            # Process upload
            upload_service = StravaUploadService(db)
            success = await upload_service.process_job(job)

            return {
                "success": success,
                "job_id": job_id,
                "activity_id": job.activity_id,
                "status": job.status,
                "strava_activity_id": job.strava_activity_id,
            }

        except Exception as e:
            logger.exception(f"Error processing job {job_id}")
            return {"success": False, "error": str(e)}


async def process_pending_uploads(ctx: dict) -> dict[str, Any]:
    """Process all pending Strava upload jobs.

    This is a scheduled task that runs periodically to process
    any pending upload jobs that are ready for retry.

    Args:
        ctx: ARQ context.

    Returns:
        Result dictionary with processing statistics.
    """
    logger.info("Starting pending uploads processor")

    processed = 0
    succeeded = 0
    failed = 0

    async with await get_db_session() as db:
        try:
            upload_service = StravaUploadService(db)

            # Get pending jobs (respecting concurrency limit)
            jobs = await upload_service.get_pending_jobs(
                limit=settings.strava_upload_concurrency
            )

            if not jobs:
                logger.debug("No pending upload jobs")
                return {"processed": 0, "succeeded": 0, "failed": 0}

            for job in jobs:
                try:
                    success = await upload_service.process_job(job)
                    processed += 1
                    if success:
                        succeeded += 1
                    else:
                        failed += 1

                    # Small delay between uploads to avoid rate limiting
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.exception(f"Error processing job {job.id}")
                    failed += 1

        except Exception as e:
            logger.exception("Error in pending uploads processor")

    logger.info(
        f"Pending uploads processor complete: "
        f"processed={processed}, succeeded={succeeded}, failed={failed}"
    )

    return {"processed": processed, "succeeded": succeeded, "failed": failed}


async def startup(ctx: dict) -> None:
    """Worker startup hook."""
    logger.info("Strava worker starting up")


async def shutdown(ctx: dict) -> None:
    """Worker shutdown hook."""
    logger.info("Strava worker shutting down")


class WorkerSettings:
    """ARQ worker configuration."""

    # Redis connection
    redis_settings = get_redis_settings()

    # Task functions
    functions = [
        process_strava_upload,
        process_pending_uploads,
    ]

    # Scheduled tasks (cron jobs)
    cron_jobs = [
        # Process pending uploads every 2 minutes
        {
            "coroutine": process_pending_uploads,
            "minute": {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58},
            "unique": True,
        },
    ]

    # Worker settings
    on_startup = startup
    on_shutdown = shutdown

    # Job settings
    max_jobs = settings.strava_upload_concurrency
    job_timeout = 300  # 5 minutes per job
    keep_result = 3600  # Keep results for 1 hour
    queue_name = "strava_uploads"


async def enqueue_upload_job(job_id: int) -> None:
    """Enqueue a specific upload job for processing.

    This can be called from the API to immediately trigger processing
    of a specific job instead of waiting for the scheduled task.

    Args:
        job_id: ID of the StravaUploadJob to process.
    """
    redis = await create_pool(get_redis_settings())
    await redis.enqueue_job("process_strava_upload", job_id)
    await redis.close()
