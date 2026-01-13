"""Cloudflare R2 storage service for FIT files."""

import gzip
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()


class R2StorageService:
    """Service for managing FIT files in Cloudflare R2."""

    def __init__(self):
        """Initialize R2 client with credentials."""
        self.account_id = os.getenv("R2_ACCOUNT_ID", "")
        self.access_key = os.getenv("R2_ACCESS_KEY", "")
        self.secret_key = os.getenv("R2_SECRET_KEY", "")
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "fit-files")

        # Initialize S3 client (R2 is S3-compatible)
        self.client = boto3.client(
            's3',
            endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='auto'  # R2 automatically selects region
        )

        # Check if bucket exists, create if not
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure the bucket exists, create if not."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            # Bucket doesn't exist, create it
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
                print(f"Created R2 bucket: {self.bucket_name}")
            except Exception as e:
                print(f"Error creating bucket: {e}")

    def _generate_key(self, user_id: int, activity_id: int) -> str:
        """Generate S3 key for FIT file.

        Args:
            user_id: User ID
            activity_id: Activity ID

        Returns:
            S3 object key with year-based organization
        """
        year = datetime.now().year
        return f"users/{user_id}/{year}/activities/{activity_id}.fit.gz"

    def compress_data(self, data: bytes) -> Tuple[bytes, float]:
        """Compress data using gzip.

        Args:
            data: Raw data to compress

        Returns:
            Tuple of (compressed data, compression ratio)
        """
        compressed = gzip.compress(data, compresslevel=6)
        ratio = (1 - len(compressed) / len(data)) * 100 if data else 0
        return compressed, ratio

    def decompress_data(self, compressed: bytes) -> bytes:
        """Decompress gzip data.

        Args:
            compressed: Compressed data

        Returns:
            Original data
        """
        return gzip.decompress(compressed)

    def calculate_hash(self, data: bytes) -> str:
        """Calculate SHA-256 hash of data.

        Args:
            data: Data to hash

        Returns:
            Hex digest of hash
        """
        return hashlib.sha256(data).hexdigest()

    async def upload_fit(
        self,
        user_id: int,
        activity_id: int,
        fit_data: bytes,
        compress: bool = True
    ) -> Dict[str, any]:
        """Upload FIT file to R2.

        Args:
            user_id: User ID
            activity_id: Activity ID
            fit_data: Raw FIT file data
            compress: Whether to compress before upload

        Returns:
            Dictionary with upload details
        """
        key = self._generate_key(user_id, activity_id)
        file_hash = self.calculate_hash(fit_data)

        # Compress if requested
        if compress:
            upload_data, compression_ratio = self.compress_data(fit_data)
            content_type = 'application/gzip'
        else:
            upload_data = fit_data
            compression_ratio = 0
            content_type = 'application/octet-stream'

        try:
            # Upload to R2
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=upload_data,
                ContentType=content_type,
                Metadata={
                    'original_size': str(len(fit_data)),
                    'file_hash': file_hash,
                    'compressed': str(compress),
                    'user_id': str(user_id),
                    'activity_id': str(activity_id)
                }
            )

            return {
                'key': key,
                'original_size': len(fit_data),
                'compressed_size': len(upload_data),
                'compression_ratio': compression_ratio,
                'file_hash': file_hash,
                'success': True
            }

        except Exception as e:
            print(f"Error uploading to R2: {e}")
            return {
                'key': key,
                'success': False,
                'error': str(e)
            }

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
            decompress: Whether to decompress after download

        Returns:
            FIT file data or None if not found
        """
        key = self._generate_key(user_id, activity_id)

        try:
            # Download from R2
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )

            data = response['Body'].read()
            metadata = response.get('Metadata', {})

            # Decompress if needed
            if decompress and metadata.get('compressed') == 'True':
                data = self.decompress_data(data)

            # Verify hash if available
            if 'file_hash' in metadata:
                calculated_hash = self.calculate_hash(data)
                if calculated_hash != metadata['file_hash']:
                    print(f"Hash mismatch for {key}")
                    return None

            return data

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"File not found: {key}")
            else:
                print(f"Error downloading from R2: {e}")
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
            Dictionary with upload URL and metadata
        """
        key = self._generate_key(user_id, activity_id)

        try:
            # Generate presigned PUT URL
            upload_url = self.client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'ContentType': 'application/gzip',
                    'Metadata': {
                        'user_id': str(user_id),
                        'activity_id': str(activity_id),
                        'uploaded_at': datetime.utcnow().isoformat()
                    }
                },
                ExpiresIn=expires_in
            )

            return {
                'upload_url': upload_url,
                'key': key,
                'expires_in': expires_in,
                'expires_at': (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
            }

        except Exception as e:
            print(f"Error generating presigned URL: {e}")
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
            Presigned download URL or None
        """
        key = self._generate_key(user_id, activity_id)

        try:
            return self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expires_in
            )
        except Exception as e:
            print(f"Error generating download URL: {e}")
            return None

    async def delete_fit(
        self,
        user_id: int,
        activity_id: int
    ) -> bool:
        """Delete FIT file from R2.

        Args:
            user_id: User ID
            activity_id: Activity ID

        Returns:
            True if deleted successfully
        """
        key = self._generate_key(user_id, activity_id)

        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except Exception as e:
            print(f"Error deleting from R2: {e}")
            return False

    async def list_user_files(
        self,
        user_id: int,
        year: Optional[int] = None
    ) -> list:
        """List all FIT files for a user.

        Args:
            user_id: User ID
            year: Optional year filter

        Returns:
            List of file metadata
        """
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
                # Get metadata for each file
                head_response = self.client.head_object(
                    Bucket=self.bucket_name,
                    Key=obj['Key']
                )

                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'metadata': head_response.get('Metadata', {})
                })

            return files

        except Exception as e:
            print(f"Error listing files: {e}")
            return []

    async def get_storage_stats(
        self,
        user_id: Optional[int] = None
    ) -> Dict[str, any]:
        """Get storage statistics.

        Args:
            user_id: Optional user ID for user-specific stats

        Returns:
            Dictionary with storage statistics
        """
        prefix = f"users/{user_id}/" if user_id else ""

        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            total_size = sum(obj['Size'] for obj in response.get('Contents', []))
            file_count = len(response.get('Contents', []))

            return {
                'total_files': file_count,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'total_size_gb': total_size / (1024 * 1024 * 1024),
                'free_tier_limit_gb': 10,
                'free_tier_used_percent': (total_size / (10 * 1024 * 1024 * 1024)) * 100
            }

        except Exception as e:
            print(f"Error getting stats: {e}")
            return {
                'error': str(e),
                'total_files': 0,
                'total_size_bytes': 0
            }


# Singleton instance
_r2_service: Optional[R2StorageService] = None


def get_r2_service() -> R2StorageService:
    """Get R2 storage service instance.

    Returns:
        R2StorageService singleton instance
    """
    global _r2_service
    if _r2_service is None:
        _r2_service = R2StorageService()
    return _r2_service