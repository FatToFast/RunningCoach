"""Strava upload service for async FIT file uploads.

This module provides the core logic for uploading FIT files to Strava,
handling retries, polling for upload completion, and tracking upload status.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.models.activity import Activity
from app.models.strava import (
    StravaSession,
    StravaSyncState,
    StravaActivityMap,
    StravaUploadJob,
    StravaUploadStatus,
)
from app.observability import get_metrics_backend

settings = get_settings()
logger = logging.getLogger(__name__)


class StravaUploadService:
    """Service for uploading activities to Strava."""

    def __init__(self, db: AsyncSession):
        """Initialize the upload service.

        Args:
            db: Database session for persistence operations.
        """
        self.db = db
        self.metrics = get_metrics_backend()

    async def enqueue_activity(
        self,
        user_id: int,
        activity_id: int,
        skip_if_exists: bool = True,
    ) -> Optional[StravaUploadJob]:
        """Queue an activity for Strava upload.

        Args:
            user_id: User ID.
            activity_id: Activity ID to upload.
            skip_if_exists: Skip if job already exists (default True).

        Returns:
            Created or existing StravaUploadJob, or None if skipped.
        """
        # Check if job already exists
        if skip_if_exists:
            existing = await self.db.execute(
                select(StravaUploadJob).where(
                    StravaUploadJob.activity_id == activity_id
                )
            )
            job = existing.scalar_one_or_none()
            if job:
                logger.debug(f"Upload job already exists for activity {activity_id}")
                return job

        # Check if already uploaded (StravaActivityMap exists)
        map_result = await self.db.execute(
            select(StravaActivityMap).where(
                StravaActivityMap.activity_id == activity_id
            )
        )
        if map_result.scalar_one_or_none():
            logger.debug(f"Activity {activity_id} already uploaded to Strava")
            return None

        # Check activity has FIT file
        activity_result = await self.db.execute(
            select(Activity).where(
                and_(
                    Activity.id == activity_id,
                    Activity.user_id == user_id,
                )
            )
        )
        activity = activity_result.scalar_one_or_none()
        if not activity or not activity.has_fit_file:
            logger.debug(f"Activity {activity_id} has no FIT file")
            return None

        # Create job with upsert (handle race condition)
        now = datetime.now(timezone.utc)
        stmt = insert(StravaUploadJob).values(
            user_id=user_id,
            activity_id=activity_id,
            status=StravaUploadStatus.QUEUED.value,
            attempts=0,
            next_retry_at=now,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["activity_id"])
        await self.db.execute(stmt)
        await self.db.commit()

        # Fetch the job
        result = await self.db.execute(
            select(StravaUploadJob).where(
                StravaUploadJob.activity_id == activity_id
            )
        )
        return result.scalar_one_or_none()

    async def enqueue_pending_activities(
        self,
        user_id: int,
        since: Optional[datetime] = None,
    ) -> int:
        """Queue all pending activities for upload.

        Args:
            user_id: User ID.
            since: Only queue activities after this time (optional).

        Returns:
            Number of activities queued.
        """
        # Find activities with FIT files that haven't been uploaded
        query = (
            select(Activity.id)
            .outerjoin(StravaActivityMap)
            .outerjoin(StravaUploadJob)
            .where(
                and_(
                    Activity.user_id == user_id,
                    Activity.has_fit_file == True,
                    StravaActivityMap.id == None,  # Not already uploaded
                    StravaUploadJob.id == None,  # Not already queued
                )
            )
        )

        if since:
            query = query.where(Activity.start_time >= since)

        result = await self.db.execute(query)
        activity_ids = [row[0] for row in result.fetchall()]

        queued_count = 0
        for activity_id in activity_ids:
            job = await self.enqueue_activity(user_id, activity_id)
            if job:
                queued_count += 1

        logger.info(f"Queued {queued_count} activities for Strava upload (user {user_id})")
        return queued_count

    async def process_job(self, job: StravaUploadJob) -> bool:
        """Process a single upload job.

        Args:
            job: The upload job to process.

        Returns:
            True if upload succeeded, False otherwise.
        """
        now = datetime.now(timezone.utc)

        # Mark as uploading
        job.status = StravaUploadStatus.UPLOADING.value
        job.started_at = now
        job.attempts += 1
        await self.db.commit()

        try:
            # Get activity and session
            activity = await self._get_activity(job.activity_id)
            session = await self._get_strava_session(job.user_id)

            if not activity:
                await self._fail_job(job, "Activity not found")
                return False

            if not session:
                await self._fail_job(job, "Strava not connected")
                return False

            # Ensure token is valid
            session = await self._ensure_valid_token(session)
            if not session:
                await self._fail_job(job, "Failed to refresh Strava token")
                return False

            # Upload FIT file
            upload_id = await self._upload_fit(activity, session.access_token)
            if not upload_id:
                await self._schedule_retry(job, "Upload failed")
                return False

            # Store upload_id and poll for completion
            job.strava_upload_id = upload_id
            job.status = StravaUploadStatus.POLLING.value
            await self.db.commit()

            # Poll for activity ID
            strava_activity_id = await self._poll_upload_status(
                upload_id, session.access_token
            )

            if strava_activity_id:
                await self._complete_job(job, strava_activity_id)
                return True
            else:
                await self._schedule_retry(job, "Upload processing not complete")
                return False

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code == 429:
                # Rate limited - schedule retry with longer delay
                await self._schedule_retry(job, error_msg, rate_limited=True)
            elif e.response.status_code in (401, 403):
                await self._fail_job(job, f"Auth error: {error_msg}")
            else:
                await self._schedule_retry(job, error_msg)
            return False

        except Exception as e:
            logger.exception(f"Error processing upload job {job.id}")
            await self._schedule_retry(job, str(e))
            return False

    async def _get_activity(self, activity_id: int) -> Optional[Activity]:
        """Get activity by ID."""
        result = await self.db.execute(
            select(Activity).where(Activity.id == activity_id)
        )
        return result.scalar_one_or_none()

    async def _get_strava_session(self, user_id: int) -> Optional[StravaSession]:
        """Get Strava session for user."""
        result = await self.db.execute(
            select(StravaSession).where(StravaSession.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _ensure_valid_token(
        self, session: StravaSession
    ) -> Optional[StravaSession]:
        """Ensure Strava token is valid, refreshing if needed."""
        if session.expires_at and session.expires_at > datetime.now(timezone.utc):
            return session

        if not session.refresh_token:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://www.strava.com/oauth/token",
                    data={
                        "client_id": settings.strava_client_id,
                        "client_secret": settings.strava_client_secret,
                        "refresh_token": session.refresh_token,
                        "grant_type": "refresh_token",
                    },
                    timeout=settings.strava_http_timeout_short_seconds,
                )
                response.raise_for_status()
                tokens = response.json()

            session.access_token = tokens["access_token"]
            session.refresh_token = tokens["refresh_token"]
            session.expires_at = datetime.fromtimestamp(
                tokens["expires_at"], tz=timezone.utc
            )
            await self.db.commit()
            return session

        except Exception as e:
            logger.exception("Failed to refresh Strava token")
            return None

    async def _upload_fit(
        self, activity: Activity, access_token: str
    ) -> Optional[int]:
        """Upload FIT file to Strava.

        Returns:
            Upload ID if successful, None otherwise.
        """
        if not activity.fit_file_path:
            return None

        fit_path = Path(activity.fit_file_path)
        if not fit_path.exists():
            logger.error(f"FIT file not found: {fit_path}")
            return None

        start_time = time.perf_counter()
        status_code = 500

        try:
            async with httpx.AsyncClient() as client:
                with fit_path.open("rb") as f:
                    files = {"file": (fit_path.name, f, "application/octet-stream")}
                    data = {
                        "data_type": "fit",
                        "name": activity.name or f"Run {activity.start_time.strftime('%Y-%m-%d')}",
                        "activity_type": "run",
                    }
                    response = await client.post(
                        "https://www.strava.com/api/v3/uploads",
                        headers={"Authorization": f"Bearer {access_token}"},
                        files=files,
                        data=data,
                        timeout=settings.strava_http_timeout_seconds,
                    )
                    status_code = response.status_code
                    response.raise_for_status()
                    result = response.json()

            return result.get("id")

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.observe_external_api("strava", "upload", status_code, duration_ms)

    async def _poll_upload_status(
        self,
        upload_id: int,
        access_token: str,
        max_attempts: int = 5,
        delay_seconds: int = 3,
    ) -> Optional[int]:
        """Poll Strava for upload completion.

        Args:
            upload_id: Strava upload ID.
            access_token: Valid access token.
            max_attempts: Maximum polling attempts.
            delay_seconds: Delay between attempts.

        Returns:
            Strava activity ID if complete, None otherwise.
        """
        for attempt in range(max_attempts):
            if attempt > 0:
                await asyncio.sleep(delay_seconds)

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://www.strava.com/api/v3/uploads/{upload_id}",
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=settings.strava_http_timeout_short_seconds,
                    )
                    if response.status_code == 200:
                        result = response.json()
                        activity_id = result.get("activity_id")
                        if activity_id:
                            return activity_id

                        # Check for error
                        error = result.get("error")
                        if error:
                            logger.warning(f"Strava upload error: {error}")
                            return None

            except Exception as e:
                logger.warning(f"Polling attempt {attempt + 1} failed: {e}")

        return None

    async def _complete_job(
        self, job: StravaUploadJob, strava_activity_id: int
    ) -> None:
        """Mark job as completed and create activity map."""
        now = datetime.now(timezone.utc)

        job.status = StravaUploadStatus.UPLOADED.value
        job.strava_activity_id = strava_activity_id
        job.completed_at = now

        # Create StravaActivityMap
        activity_map = StravaActivityMap(
            activity_id=job.activity_id,
            strava_activity_id=strava_activity_id,
            uploaded_at=now,
        )
        self.db.add(activity_map)

        # Update sync state
        await self._update_sync_state(job.user_id, success=True)

        await self.db.commit()
        logger.info(
            f"Strava upload complete: job={job.id}, activity={job.activity_id}, "
            f"strava_id={strava_activity_id}"
        )

    async def _fail_job(self, job: StravaUploadJob, error: str) -> None:
        """Mark job as permanently failed."""
        now = datetime.now(timezone.utc)
        job.status = StravaUploadStatus.FAILED.value
        job.last_error = error
        job.last_error_at = now
        job.completed_at = now
        await self.db.commit()
        logger.error(f"Strava upload failed: job={job.id}, error={error}")

    async def _schedule_retry(
        self,
        job: StravaUploadJob,
        error: str,
        rate_limited: bool = False,
    ) -> None:
        """Schedule job for retry."""
        now = datetime.now(timezone.utc)
        job.last_error = error
        job.last_error_at = now

        # Check max retries
        max_retries = settings.strava_upload_max_retries
        if job.attempts >= max_retries:
            await self._fail_job(job, f"Max retries ({max_retries}) exceeded. Last: {error}")
            return

        # Calculate retry delay
        retry_delays = [int(d) for d in settings.strava_upload_retry_delays.split(",")]
        delay_index = min(job.attempts - 1, len(retry_delays) - 1)
        delay_seconds = retry_delays[delay_index]

        # Double delay if rate limited
        if rate_limited:
            delay_seconds *= 2

        from datetime import timedelta
        job.next_retry_at = now + timedelta(seconds=delay_seconds)
        job.status = StravaUploadStatus.QUEUED.value

        await self.db.commit()
        logger.info(
            f"Strava upload retry scheduled: job={job.id}, attempt={job.attempts}, "
            f"next_retry={job.next_retry_at}"
        )

    async def _update_sync_state(self, user_id: int, success: bool) -> None:
        """Update Strava sync state."""
        now = datetime.now(timezone.utc)

        stmt = insert(StravaSyncState).values(
            user_id=user_id,
            last_sync_at=now,
            last_success_at=now if success else None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "last_sync_at": now,
                "last_success_at": now if success else StravaSyncState.last_success_at,
                "updated_at": now,
            },
        )
        await self.db.execute(stmt)

    async def get_pending_jobs(self, limit: int = 10) -> list[StravaUploadJob]:
        """Get pending jobs ready for processing.

        Args:
            limit: Maximum number of jobs to return.

        Returns:
            List of pending jobs.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(StravaUploadJob)
            .where(
                and_(
                    StravaUploadJob.status == StravaUploadStatus.QUEUED.value,
                    StravaUploadJob.next_retry_at <= now,
                )
            )
            .order_by(StravaUploadJob.next_retry_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_job_stats(self, user_id: int) -> dict:
        """Get upload job statistics for a user.

        Args:
            user_id: User ID.

        Returns:
            Dictionary with job counts by status.
        """
        from sqlalchemy import func

        result = await self.db.execute(
            select(
                StravaUploadJob.status,
                func.count(StravaUploadJob.id),
            )
            .where(StravaUploadJob.user_id == user_id)
            .group_by(StravaUploadJob.status)
        )

        stats = {status.value: 0 for status in StravaUploadStatus}
        for status, count in result.fetchall():
            stats[status] = count

        return stats
