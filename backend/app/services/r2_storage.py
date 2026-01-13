"""Cloudflare R2 storage service for FIT files.

This module provides S3-compatible storage for FIT files using Cloudflare R2.
It supports compression, hash verification, and presigned URLs for direct uploads.
"""

import gzip
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.debug_utils import CloudMigrationDebug, trace_storage

logger = logging.getLogger(__name__)
settings = get_settings()


class R2StorageService:
    """Service for managing FIT files in Cloudflare R2.

    This service provides:
    - Upload/download with automatic gzip compression
    - Presigned URLs for direct client uploads (bypasses server)
    - SHA-256 hash verification
    - Storage statistics and quota tracking
    """

    def __init__(self):
        """Initialize R2 client with credentials from settings."""
        self._client = None
        self._initialized = False
        self._init_error: Optional[str] = None

    def _ensure_initialized(self) -> bool:
        """Lazy initialization of boto3 client."""
        if self._initialized:
            return self._client is not None

        self._initialized = True

        if not settings.r2_enabled:
            self._init_error = "R2 storage not configured (missing credentials)"
            logger.warning(self._init_error)
            return False

        try:
            # Configure boto3 client with R2-specific settings
            boto_config = BotoConfig(
                signature_version='s3v4',
                retries={'max_attempts': 3, 'mode': 'adaptive'},
                connect_timeout=10,
                read_timeout=30,
            )

            self._client = boto3.client(
                's3',
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key,
                aws_secret_access_key=settings.r2_secret_key,
                region_name='auto',
                config=boto_config
            )

            # Verify bucket exists (create if not)
            self._ensure_bucket_exists()
            logger.info(f"R2 storage initialized: bucket={settings.r2_bucket_name}")
            return True

        except Exception as e:
            self._init_error = f"Failed to initialize R2 client: {e}"
            logger.error(self._init_error)
            return False

    @property
    def client(self):
        """Get boto3 client, initializing if needed."""
        self._ensure_initialized()
        return self._client

    @property
    def bucket_name(self) -> str:
        """Get bucket name from settings."""
        return settings.r2_bucket_name

    @property
    def is_available(self) -> bool:
        """Check if R2 storage is available."""
        return self._ensure_initialized()

    def _ensure_bucket_exists(self):
        """Ensure the bucket exists, create if not."""
        if not self._client:
            return

        try:
            self._client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"R2 bucket exists: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ('404', 'NoSuchBucket'):
                try:
                    self._client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created R2 bucket: {self.bucket_name}")
                except Exception as create_error:
                    logger.error(f"Failed to create R2 bucket: {create_error}")
                    raise
            else:
                logger.error(f"Error checking R2 bucket: {e}")
                raise

    def _generate_key(self, user_id: int, activity_id: int, year: Optional[int] = None) -> str:
        """Generate S3 key for FIT file.

        Args:
            user_id: User ID
            activity_id: Activity ID
            year: Year for organization (defaults to current year)

        Returns:
            S3 object key with year-based organization
        """
        if year is None:
            year = datetime.now(timezone.utc).year
        return f"users/{user_id}/{year}/activities/{activity_id}.fit.gz"

    def compress_data(self, data: bytes) -> Tuple[bytes, float]:
        """Compress data using gzip.

        Args:
            data: Raw data to compress

        Returns:
            Tuple of (compressed data, compression ratio as percentage)
        """
        if not data:
            return b'', 0.0

        compressed = gzip.compress(data, compresslevel=6)
        ratio = (1 - len(compressed) / len(data)) * 100
        logger.debug(f"Compressed {len(data)} -> {len(compressed)} bytes ({ratio:.1f}% reduction)")
        return compressed, ratio

    def decompress_data(self, compressed: bytes) -> bytes:
        """Decompress gzip data.

        Args:
            compressed: Compressed data

        Returns:
            Original decompressed data
        """
        return gzip.decompress(compressed)

    @staticmethod
    def calculate_hash(data: bytes) -> str:
        """Calculate SHA-256 hash of data.

        Args:
            data: Data to hash

        Returns:
            Hex digest of SHA-256 hash
        """
        return hashlib.sha256(data).hexdigest()

    async def upload_fit(
        self,
        user_id: int,
        activity_id: int,
        fit_data: bytes,
        compress: bool = True
    ) -> Dict[str, Any]:
        """Upload FIT file to R2.

        Args:
            user_id: User ID
            activity_id: Activity ID
            fit_data: Raw FIT file data
            compress: Whether to compress before upload (default True)

        Returns:
            Dictionary with upload details including key, sizes, hash, and success status
        """
        if not self.is_available:
            logger.error(f"R2 not available: {self._init_error}")
            return {'success': False, 'error': self._init_error or 'R2 not configured'}

        key = self._generate_key(user_id, activity_id)
        file_hash = self.calculate_hash(fit_data)
        original_size = len(fit_data)

        # Compress if requested
        if compress:
            upload_data, compression_ratio = self.compress_data(fit_data)
            content_type = 'application/gzip'
        else:
            upload_data = fit_data
            compression_ratio = 0.0
            content_type = 'application/octet-stream'

        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=upload_data,
                ContentType=content_type,
                Metadata={
                    'original_size': str(original_size),
                    'file_hash': file_hash,
                    'compressed': str(compress).lower(),
                    'user_id': str(user_id),
                    'activity_id': str(activity_id),
                    'uploaded_at': datetime.now(timezone.utc).isoformat()
                }
            )

            logger.info(
                f"Uploaded FIT to R2: key={key}, "
                f"original={original_size}, compressed={len(upload_data)}, "
                f"ratio={compression_ratio:.1f}%"
            )

            CloudMigrationDebug.log_r2_operation(
                operation="upload",
                user_id=user_id,
                activity_id=activity_id,
                success=True,
                details={
                    "key": key,
                    "original_size": original_size,
                    "compressed_size": len(upload_data),
                    "compression_ratio": round(compression_ratio, 1),
                }
            )

            return {
                'key': key,
                'original_size': original_size,
                'compressed_size': len(upload_data),
                'compression_ratio': compression_ratio,
                'file_hash': file_hash,
                'success': True
            }

        except ClientError as e:
            error_msg = f"R2 upload failed: {e.response.get('Error', {}).get('Message', str(e))}"
            logger.error(error_msg)
            CloudMigrationDebug.log_r2_operation(
                operation="upload",
                user_id=user_id,
                activity_id=activity_id,
                success=False,
                error=error_msg,
            )
            return {'key': key, 'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"Unexpected error uploading to R2: {e}"
            logger.error(error_msg)
            return {'key': key, 'success': False, 'error': error_msg}

    async def download_fit(
        self,
        user_id: int,
        activity_id: int,
        decompress: bool = True
    ) -> Optional[bytes]:
        """Download FIT file from R2.

        Args:
            user_id: User ID
            activity_id: Activity ID
            decompress: Whether to decompress after download (default True)

        Returns:
            FIT file data or None if not found
        """
        if not self.is_available:
            logger.error(f"R2 not available: {self._init_error}")
            return None

        key = self._generate_key(user_id, activity_id)

        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            data = response['Body'].read()
            metadata = response.get('Metadata', {})

            # Decompress if needed
            if decompress and metadata.get('compressed', 'false').lower() == 'true':
                data = self.decompress_data(data)

            # Verify hash if available
            expected_hash = metadata.get('file_hash')
            if expected_hash:
                actual_hash = self.calculate_hash(data)
                if actual_hash != expected_hash:
                    logger.error(f"Hash mismatch for {key}: expected={expected_hash}, actual={actual_hash}")
                    return None

            logger.debug(f"Downloaded FIT from R2: key={key}, size={len(data)}")
            CloudMigrationDebug.log_r2_operation(
                operation="download",
                user_id=user_id,
                activity_id=activity_id,
                success=True,
                details={"key": key, "size": len(data)},
            )
            return data

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                logger.warning(f"FIT file not found in R2: {key}")
            else:
                logger.error(f"R2 download failed: {e}")
            CloudMigrationDebug.log_r2_operation(
                operation="download",
                user_id=user_id,
                activity_id=activity_id,
                success=False,
                error=f"ClientError: {error_code}",
            )
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading from R2: {e}")
            return None

    def generate_presigned_upload_url(
        self,
        user_id: int,
        activity_id: int,
        expires_in: int = 3600
    ) -> Dict[str, str]:
        """Generate presigned URL for direct client upload.

        Args:
            user_id: User ID
            activity_id: Activity ID
            expires_in: URL expiration in seconds (default 1 hour)

        Returns:
            Dictionary with upload_url, key, expires_at, and expires_in
        """
        if not self.is_available:
            logger.error(f"R2 not available for presigned URL: {self._init_error}")
            return {}

        key = self._generate_key(user_id, activity_id)
        now = datetime.now(timezone.utc)

        try:
            upload_url = self.client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'ContentType': 'application/gzip',
                },
                ExpiresIn=expires_in
            )

            logger.info(f"Generated presigned upload URL for key={key}, expires_in={expires_in}s")

            return {
                'upload_url': upload_url,
                'key': key,
                'expires_in': expires_in,
                'expires_at': (now + timedelta(seconds=expires_in)).isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to generate presigned upload URL: {e}")
            return {}

    def generate_presigned_download_url(
        self,
        user_id: int,
        activity_id: int,
        expires_in: int = 300
    ) -> Optional[str]:
        """Generate presigned URL for download.

        Args:
            user_id: User ID
            activity_id: Activity ID
            expires_in: URL expiration in seconds (default 5 minutes)

        Returns:
            Presigned download URL or None on failure
        """
        if not self.is_available:
            logger.error(f"R2 not available for presigned URL: {self._init_error}")
            return None

        key = self._generate_key(user_id, activity_id)

        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expires_in
            )
            logger.debug(f"Generated presigned download URL for key={key}")
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned download URL: {e}")
            return None

    async def delete_fit(self, user_id: int, activity_id: int) -> bool:
        """Delete FIT file from R2.

        Args:
            user_id: User ID
            activity_id: Activity ID

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.is_available:
            logger.error(f"R2 not available: {self._init_error}")
            return False

        key = self._generate_key(user_id, activity_id)

        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted FIT from R2: key={key}")
            CloudMigrationDebug.log_r2_operation(
                operation="delete",
                user_id=user_id,
                activity_id=activity_id,
                success=True,
                details={"key": key},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete from R2: {e}")
            CloudMigrationDebug.log_r2_operation(
                operation="delete",
                user_id=user_id,
                activity_id=activity_id,
                success=False,
                error=str(e),
            )
            return False

    async def list_user_files(
        self,
        user_id: int,
        year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List all FIT files for a user.

        Args:
            user_id: User ID
            year: Optional year filter

        Returns:
            List of file metadata dictionaries
        """
        if not self.is_available:
            logger.error(f"R2 not available: {self._init_error}")
            return []

        prefix = f"users/{user_id}/"
        if year:
            prefix += f"{year}/"

        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                })

            logger.debug(f"Listed {len(files)} files for user {user_id}")
            return files

        except Exception as e:
            logger.error(f"Failed to list user files: {e}")
            return []

    async def get_storage_stats(
        self,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get storage statistics.

        Args:
            user_id: Optional user ID for user-specific stats

        Returns:
            Dictionary with storage statistics
        """
        if not self.is_available:
            return {
                'error': self._init_error or 'R2 not configured',
                'total_files': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0.0,
                'total_size_gb': 0.0,
                'free_tier_limit_gb': 10,
                'free_tier_used_percent': 0.0
            }

        prefix = f"users/{user_id}/" if user_id else ""

        try:
            # Handle pagination for large buckets
            total_size = 0
            file_count = 0
            paginator = self.client.get_paginator('list_objects_v2')

            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get('Contents', []):
                    total_size += obj['Size']
                    file_count += 1

            free_tier_gb = 10
            total_gb = total_size / (1024 ** 3)

            stats = {
                'total_files': file_count,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 ** 2),
                'total_size_gb': total_gb,
                'free_tier_limit_gb': free_tier_gb,
                'free_tier_used_percent': (total_gb / free_tier_gb) * 100,
                'free_tier_remaining_gb': max(0, free_tier_gb - total_gb)
            }

            logger.debug(f"Storage stats: {file_count} files, {total_gb:.3f} GB")
            return stats

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                'error': str(e),
                'total_files': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0.0,
                'total_size_gb': 0.0,
                'free_tier_limit_gb': 10,
                'free_tier_used_percent': 0.0
            }


# Singleton instance with lazy initialization
_r2_service: Optional[R2StorageService] = None


def get_r2_service() -> R2StorageService:
    """Get R2 storage service singleton instance.

    Returns:
        R2StorageService instance
    """
    global _r2_service
    if _r2_service is None:
        _r2_service = R2StorageService()
    return _r2_service
