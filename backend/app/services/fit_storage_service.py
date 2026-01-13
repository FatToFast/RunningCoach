"""FIT File Storage Service - Handles DB storage of FIT files."""

import gzip
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.garmin import GarminRawFile
from app.models.activity import Activity


class FitStorageService:
    """Service for storing and retrieving FIT files from database."""

    @staticmethod
    def compress_file(file_content: bytes, compression: str = "gzip") -> bytes:
        """Compress file content.

        Args:
            file_content: Raw file bytes
            compression: Compression type (gzip, zstd, none)

        Returns:
            Compressed bytes
        """
        if compression == "gzip":
            return gzip.compress(file_content, compresslevel=6)
        elif compression == "zstd":
            # Optional: Use zstandard for better compression
            # import zstandard as zstd
            # cctx = zstd.ZstdCompressor(level=3)
            # return cctx.compress(file_content)
            return gzip.compress(file_content, compresslevel=6)
        else:
            return file_content

    @staticmethod
    def decompress_file(compressed: bytes, compression: str = "gzip") -> bytes:
        """Decompress file content.

        Args:
            compressed: Compressed bytes
            compression: Compression type used

        Returns:
            Original file bytes
        """
        if compression == "gzip":
            return gzip.decompress(compressed)
        elif compression == "zstd":
            # import zstandard as zstd
            # dctx = zstd.ZstdDecompressor()
            # return dctx.decompress(compressed)
            return gzip.decompress(compressed)
        else:
            return compressed

    @staticmethod
    def calculate_hash(file_content: bytes) -> str:
        """Calculate SHA-256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()

    async def store_fit_file_to_db(
        self,
        db: AsyncSession,
        garmin_file: GarminRawFile,
        file_content: bytes,
        compression: str = "gzip"
    ) -> None:
        """Store FIT file content in database.

        Args:
            db: Database session
            garmin_file: GarminRawFile record
            file_content: Raw FIT file bytes
            compression: Compression type to use
        """
        # Compress the file
        compressed = self.compress_file(file_content, compression)

        # Calculate hash
        file_hash = self.calculate_hash(file_content)

        # Update the record
        garmin_file.file_content = compressed
        garmin_file.file_size = len(file_content)
        garmin_file.file_hash = file_hash
        garmin_file.compression_type = compression

        # Clear file_path as it's now in DB
        garmin_file.file_path = None

        await db.commit()

        print(f"Stored FIT file to DB: {len(file_content)} bytes -> "
              f"{len(compressed)} bytes ({compression}), "
              f"compression ratio: {len(compressed)/len(file_content)*100:.1f}%")

    async def retrieve_fit_file_from_db(
        self,
        db: AsyncSession,
        garmin_file: GarminRawFile
    ) -> Optional[bytes]:
        """Retrieve FIT file content from database.

        Args:
            db: Database session
            garmin_file: GarminRawFile record with file_content

        Returns:
            Original FIT file bytes or None if not found
        """
        if not garmin_file.file_content:
            return None

        # Decompress the file
        compression = garmin_file.compression_type or "gzip"
        file_content = self.decompress_file(garmin_file.file_content, compression)

        # Verify hash if available
        if garmin_file.file_hash:
            calculated_hash = self.calculate_hash(file_content)
            if calculated_hash != garmin_file.file_hash:
                raise ValueError(f"File hash mismatch! Expected {garmin_file.file_hash}, "
                               f"got {calculated_hash}")

        return file_content

    async def migrate_file_to_db(
        self,
        db: AsyncSession,
        garmin_file: GarminRawFile,
        delete_original: bool = False
    ) -> bool:
        """Migrate existing file from filesystem to database.

        Args:
            db: Database session
            garmin_file: GarminRawFile record with file_path
            delete_original: Whether to delete the original file after migration

        Returns:
            True if migration successful, False otherwise
        """
        if not garmin_file.file_path:
            return False

        file_path = Path(garmin_file.file_path)
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return False

        try:
            # Read file content
            file_content = file_path.read_bytes()

            # Store to DB
            await self.store_fit_file_to_db(db, garmin_file, file_content)

            # Optionally delete original file
            if delete_original:
                file_path.unlink()
                print(f"Deleted original file: {file_path}")

            return True

        except Exception as e:
            print(f"Error migrating file {file_path}: {e}")
            return False

    async def get_or_migrate_fit_file(
        self,
        db: AsyncSession,
        garmin_file: GarminRawFile
    ) -> Optional[bytes]:
        """Get FIT file from DB or migrate from filesystem if needed.

        Args:
            db: Database session
            garmin_file: GarminRawFile record

        Returns:
            FIT file bytes or None
        """
        # First try to get from DB
        if garmin_file.file_content:
            return await self.retrieve_fit_file_from_db(db, garmin_file)

        # If not in DB but file path exists, migrate it
        if garmin_file.file_path:
            success = await self.migrate_file_to_db(db, garmin_file, delete_original=False)
            if success:
                return await self.retrieve_fit_file_from_db(db, garmin_file)

        return None