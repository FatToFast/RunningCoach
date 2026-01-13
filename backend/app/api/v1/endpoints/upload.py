"""Upload endpoints for direct FIT file uploads to R2.

This module provides endpoints for:
- Generating presigned URLs for direct client-to-R2 uploads
- Confirming upload completion and triggering analysis
- Managing storage statistics
- Downloading and deleting FIT files
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.hybrid_auth import get_current_user
from app.models.activity import Activity
from app.models.user import User
from app.services.r2_storage import R2StorageService, get_r2_service

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# ======================
# Request/Response Models
# ======================

class UploadUrlRequest(BaseModel):
    """Request for generating presigned upload URL."""
    activity_id: Optional[int] = Field(None, description="Existing activity ID (optional)")
    filename: Optional[str] = Field(None, description="Original filename for reference")
    file_size: Optional[int] = Field(None, ge=0, description="Expected file size in bytes")


class UploadUrlResponse(BaseModel):
    """Response with presigned upload URL."""
    upload_url: str
    key: str
    activity_id: int
    expires_at: str
    expires_in: int


class UploadCompleteRequest(BaseModel):
    """Request to confirm upload completion."""
    activity_id: int
    file_size: int = Field(..., ge=0, description="Actual uploaded file size")
    checksum: Optional[str] = Field(None, description="SHA-256 checksum of uploaded file")


class UploadCompleteResponse(BaseModel):
    """Response after upload completion."""
    status: str
    activity_id: int
    analysis_job_id: Optional[str] = None
    message: Optional[str] = None


class StorageStatsResponse(BaseModel):
    """Storage statistics response."""
    user_id: int
    total_files: int
    total_size_mb: float
    total_size_gb: float
    free_tier_limit_gb: int
    free_tier_used_percent: float
    free_tier_remaining_gb: float


# ======================
# Endpoints
# ======================

@router.post("/url", response_model=UploadUrlResponse)
async def generate_upload_url(
    request: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    r2: R2StorageService = Depends(get_r2_service)
) -> UploadUrlResponse:
    """Generate presigned URL for direct FIT file upload to R2.

    This endpoint generates a presigned URL that allows direct upload
    from the client to R2, bypassing the server for better performance.

    Args:
        request: Upload request details
        current_user: Authenticated user
        db: Database session
        r2: R2 storage service

    Returns:
        Presigned upload URL and metadata
    """
    # Check if R2 is available
    if not r2.is_available:
        logger.error("R2 storage not available for upload URL generation")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloud storage not available"
        )

    # If activity_id provided, verify ownership
    if request.activity_id:
        stmt = select(Activity).where(
            Activity.id == request.activity_id,
            Activity.user_id == current_user.id
        )
        result = await db.execute(stmt)
        activity = result.scalar_one_or_none()

        if not activity:
            logger.warning(f"Activity not found: id={request.activity_id}, user={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found"
            )

        logger.debug(f"Using existing activity: id={activity.id}")
    else:
        # Create new activity placeholder for the upload
        now = datetime.now(timezone.utc)
        activity = Activity(
            user_id=current_user.id,
            garmin_id=0,  # Will be updated from FIT file
            name=request.filename or "FIT Upload",
            activity_type="running",
            start_time=now,
        )
        db.add(activity)
        await db.commit()
        await db.refresh(activity)
        logger.info(f"Created placeholder activity: id={activity.id}, user={current_user.id}")

    # Generate presigned upload URL
    upload_info = r2.generate_presigned_upload_url(
        user_id=current_user.id,
        activity_id=activity.id,
        expires_in=3600  # 1 hour
    )

    if not upload_info:
        logger.error(f"Failed to generate presigned URL for activity {activity.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL"
        )

    # Update activity with R2 key and pending status
    activity.r2_key = upload_info['key']
    activity.storage_provider = 'r2'
    activity.storage_metadata = {
        'status': 'pending',
        'requested_at': datetime.now(timezone.utc).isoformat(),
        'expected_size': request.file_size,
        'filename': request.filename
    }
    await db.commit()

    logger.info(
        f"Generated presigned upload URL: activity={activity.id}, "
        f"key={upload_info['key']}, user={current_user.id}"
    )

    return UploadUrlResponse(
        upload_url=upload_info['upload_url'],
        key=upload_info['key'],
        activity_id=activity.id,
        expires_at=upload_info['expires_at'],
        expires_in=upload_info['expires_in']
    )


@router.post("/complete", response_model=UploadCompleteResponse)
async def confirm_upload_complete(
    request: UploadCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    r2: R2StorageService = Depends(get_r2_service)
) -> UploadCompleteResponse:
    """Confirm FIT file upload completion and trigger analysis.

    Call this endpoint after successfully uploading to the presigned URL.
    It updates the activity status and optionally queues analysis.

    Args:
        request: Upload completion details
        current_user: Authenticated user
        db: Database session
        r2: R2 storage service

    Returns:
        Upload confirmation and analysis job ID if queued
    """
    # Verify activity ownership
    stmt = select(Activity).where(
        Activity.id == request.activity_id,
        Activity.user_id == current_user.id
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()

    if not activity:
        logger.warning(f"Activity not found for completion: id={request.activity_id}, user={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found"
        )

    # Update activity metadata
    metadata = activity.storage_metadata or {}
    metadata.update({
        'status': 'uploaded',
        'uploaded_at': datetime.now(timezone.utc).isoformat(),
        'file_size': request.file_size,
        'checksum': request.checksum
    })
    activity.storage_metadata = metadata
    activity.has_fit_file = True
    activity.fit_file_size = request.file_size

    await db.commit()

    logger.info(
        f"Upload completed: activity={activity.id}, size={request.file_size}, "
        f"user={current_user.id}"
    )

    # Try to enqueue async analysis job
    job_id = None
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        pool = await create_pool(redis_settings)
        job = await pool.enqueue_job(
            'analyze_fit',
            activity_id=activity.id,
            user_id=current_user.id
        )
        job_id = job.job_id if job else None
        logger.info(f"Enqueued analysis job: job_id={job_id}, activity={activity.id}")
    except Exception as e:
        logger.warning(f"Failed to enqueue analysis job: {e}")
        # Continue without async processing - analysis can be triggered later

    return UploadCompleteResponse(
        status="uploaded",
        activity_id=activity.id,
        analysis_job_id=job_id,
        message="Upload confirmed" + (f", analysis job queued: {job_id}" if job_id else "")
    )


@router.get("/activity/{activity_id}/download-url")
async def get_download_url(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    r2: R2StorageService = Depends(get_r2_service)
) -> Dict[str, Any]:
    """Get presigned download URL for FIT file.

    Args:
        activity_id: Activity ID
        current_user: Authenticated user
        db: Database session
        r2: R2 storage service

    Returns:
        Presigned download URL with metadata
    """
    # Verify activity ownership
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.user_id == current_user.id
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found"
        )

    if not activity.r2_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FIT file not found in cloud storage"
        )

    # Generate presigned download URL
    download_url = r2.generate_presigned_download_url(
        user_id=current_user.id,
        activity_id=activity_id,
        expires_in=300  # 5 minutes
    )

    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )

    logger.debug(f"Generated download URL: activity={activity_id}, user={current_user.id}")

    return {
        'download_url': download_url,
        'expires_in': 300,
        'content_type': 'application/gzip',
        'file_size': activity.fit_file_size
    }


@router.get("/stats", response_model=StorageStatsResponse)
async def get_storage_stats(
    current_user: User = Depends(get_current_user),
    r2: R2StorageService = Depends(get_r2_service)
) -> StorageStatsResponse:
    """Get storage statistics for current user.

    Args:
        current_user: Authenticated user
        r2: R2 storage service

    Returns:
        Storage usage statistics including free tier information
    """
    stats = await r2.get_storage_stats(user_id=current_user.id)

    if 'error' in stats:
        logger.warning(f"Error getting storage stats: {stats['error']}")

    return StorageStatsResponse(
        user_id=current_user.id,
        total_files=stats.get('total_files', 0),
        total_size_mb=round(stats.get('total_size_mb', 0), 2),
        total_size_gb=round(stats.get('total_size_gb', 0), 3),
        free_tier_limit_gb=stats.get('free_tier_limit_gb', 10),
        free_tier_used_percent=round(stats.get('free_tier_used_percent', 0), 2),
        free_tier_remaining_gb=round(stats.get('free_tier_remaining_gb', 10), 3)
    )


@router.delete("/activity/{activity_id}/fit")
async def delete_fit_file(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    r2: R2StorageService = Depends(get_r2_service)
) -> Dict[str, Any]:
    """Delete FIT file from R2 storage.

    Args:
        activity_id: Activity ID
        current_user: Authenticated user
        db: Database session
        r2: R2 storage service

    Returns:
        Deletion status
    """
    # Verify activity ownership
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.user_id == current_user.id
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found"
        )

    if not activity.r2_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No FIT file to delete"
        )

    # Delete from R2
    deleted = await r2.delete_fit(
        user_id=current_user.id,
        activity_id=activity_id
    )

    if deleted:
        # Update activity
        old_key = activity.r2_key
        activity.r2_key = None
        activity.has_fit_file = False
        activity.storage_metadata = {
            'deleted_at': datetime.now(timezone.utc).isoformat(),
            'deleted_key': old_key
        }
        await db.commit()

        logger.info(f"Deleted FIT file: activity={activity_id}, key={old_key}, user={current_user.id}")
        return {'status': 'deleted', 'activity_id': activity_id}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file from storage"
        )


# ======================
# Health Check
# ======================

@router.get("/health")
async def upload_health(
    r2: R2StorageService = Depends(get_r2_service)
) -> Dict[str, Any]:
    """Health check for upload service.

    Returns:
        Health status and R2 availability
    """
    return {
        "status": "ok",
        "r2_available": r2.is_available,
        "r2_bucket": settings.r2_bucket_name if r2.is_available else None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
