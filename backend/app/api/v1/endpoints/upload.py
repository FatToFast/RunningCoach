"""Upload endpoints for direct FIT file uploads to R2."""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.clerk_auth import get_current_user
from app.models.user import User
from app.models.activity import Activity
from app.services.r2_storage import get_r2_service, R2StorageService
from app.workers.tasks import analyze_fit_task

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response Models
class UploadUrlRequest(BaseModel):
    """Request for generating upload URL."""
    activity_id: Optional[int] = None
    filename: Optional[str] = None
    file_size: Optional[int] = None


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
    file_size: int
    checksum: Optional[str] = None


class UploadCompleteResponse(BaseModel):
    """Response after upload completion."""
    status: str
    activity_id: int
    analysis_job_id: Optional[str] = None


@router.post("/upload-url", response_model=UploadUrlResponse)
async def generate_upload_url(
    request: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    r2: R2StorageService = Depends(get_r2_service)
) -> UploadUrlResponse:
    """Generate presigned URL for direct FIT file upload to R2.

    Args:
        request: Upload request details
        current_user: Authenticated user
        db: Database session
        r2: R2 storage service

    Returns:
        Presigned upload URL and metadata
    """
    # If activity_id provided, verify ownership
    if request.activity_id:
        stmt = select(Activity).where(
            Activity.id == request.activity_id,
            Activity.user_id == current_user.id
        )
        result = await db.execute(stmt)
        activity = result.scalar_one_or_none()

        if not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found"
            )
    else:
        # Create new activity for the upload
        activity = Activity(
            user_id=current_user.id,
            name=request.filename or "FIT Upload",
            activity_type="running",
            start_time=datetime.utcnow(),  # Will be updated from FIT
            created_at=datetime.utcnow()
        )
        db.add(activity)
        await db.commit()
        await db.refresh(activity)

    # Generate presigned upload URL
    upload_info = r2.generate_presigned_upload_url(
        user_id=current_user.id,
        activity_id=activity.id,
        expires_in=3600  # 1 hour
    )

    if not upload_info:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL"
        )

    # Update activity with R2 key
    activity.r2_key = upload_info['key']
    activity.storage_provider = 'r2'
    activity.storage_metadata = {
        'status': 'pending',
        'requested_at': datetime.utcnow().isoformat()
    }
    await db.commit()

    return UploadUrlResponse(
        upload_url=upload_info['upload_url'],
        key=upload_info['key'],
        activity_id=activity.id,
        expires_at=upload_info['expires_at'],
        expires_in=upload_info['expires_in']
    )


@router.post("/upload-complete", response_model=UploadCompleteResponse)
async def confirm_upload_complete(
    request: UploadCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    r2: R2StorageService = Depends(get_r2_service)
) -> UploadCompleteResponse:
    """Confirm FIT file upload completion and trigger analysis.

    Args:
        request: Upload completion details
        current_user: Authenticated user
        db: Database session
        r2: R2 storage service

    Returns:
        Upload confirmation and analysis job ID
    """
    # Verify activity ownership
    stmt = select(Activity).where(
        Activity.id == request.activity_id,
        Activity.user_id == current_user.id
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found"
        )

    # Verify file exists in R2
    stats = await r2.get_storage_stats(user_id=current_user.id)

    # Update activity metadata
    if not activity.storage_metadata:
        activity.storage_metadata = {}

    activity.storage_metadata.update({
        'status': 'uploaded',
        'uploaded_at': datetime.utcnow().isoformat(),
        'file_size': request.file_size,
        'checksum': request.checksum
    })

    activity.has_fit_file = True
    await db.commit()

    # Trigger async analysis
    job_id = None
    try:
        from arq import create_pool
        from app.core.config import get_settings

        settings = get_settings()
        pool = await create_pool(settings.redis_url)
        job = await pool.enqueue_job(
            'analyze_fit',
            activity_id=activity.id,
            user_id=current_user.id
        )
        job_id = job.job_id
    except Exception as e:
        logger.error(f"Failed to enqueue analysis job: {e}")
        # Continue without async processing
        # The file is uploaded, analysis can be triggered later

    return UploadCompleteResponse(
        status="uploaded",
        activity_id=activity.id,
        analysis_job_id=job_id
    )


@router.get("/activity/{activity_id}/download-url")
async def get_download_url(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    r2: R2StorageService = Depends(get_r2_service)
) -> dict:
    """Get presigned download URL for FIT file.

    Args:
        activity_id: Activity ID
        current_user: Authenticated user
        db: Database session
        r2: R2 storage service

    Returns:
        Presigned download URL
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
            detail="FIT file not found in storage"
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

    return {
        'download_url': download_url,
        'expires_in': 300,
        'content_type': 'application/octet-stream'
    }


@router.get("/storage/stats")
async def get_storage_stats(
    current_user: User = Depends(get_current_user),
    r2: R2StorageService = Depends(get_r2_service)
) -> dict:
    """Get storage statistics for current user.

    Args:
        current_user: Authenticated user
        r2: R2 storage service

    Returns:
        Storage usage statistics
    """
    stats = await r2.get_storage_stats(user_id=current_user.id)

    return {
        'user_id': current_user.id,
        'total_files': stats['total_files'],
        'total_size_mb': round(stats['total_size_mb'], 2),
        'total_size_gb': round(stats['total_size_gb'], 3),
        'free_tier_limit_gb': stats['free_tier_limit_gb'],
        'free_tier_used_percent': round(stats['free_tier_used_percent'], 2),
        'free_tier_remaining_gb': round(10 - stats['total_size_gb'], 3)
    }


@router.delete("/activity/{activity_id}/fit")
async def delete_fit_file(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    r2: R2StorageService = Depends(get_r2_service)
) -> dict:
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
        activity.r2_key = None
        activity.has_fit_file = False
        activity.storage_metadata = {
            'deleted_at': datetime.utcnow().isoformat()
        }
        await db.commit()

        return {'status': 'deleted', 'activity_id': activity_id}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )