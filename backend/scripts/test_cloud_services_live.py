#!/usr/bin/env python3
"""Live integration tests for cloud services.

This script tests actual connections to:
1. Clerk - JWT authentication
2. Cloudflare R2 - Object storage
3. Neon - PostgreSQL database

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/test_cloud_services_live.py [--clerk] [--r2] [--neon] [--all]

Prerequisites:
    Set environment variables in .env:
    - CLERK_PUBLISHABLE_KEY
    - CLERK_SECRET_KEY
    - R2_ACCOUNT_ID
    - R2_ACCESS_KEY_ID (mapped to R2_ACCESS_KEY)
    - R2_SECRET_ACCESS_KEY (mapped to R2_SECRET_KEY)
    - R2_BUCKET_NAME
    - DATABASE_URL (with neon.tech for Neon)
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")


# ============================================================================
# Test Result Tracking
# ============================================================================

class TestResult:
    """Container for test results."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def add(self, name: str, status: str, message: str = "", details: Dict = None):
        """Add a test result."""
        self.results.append({
            "name": name,
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Print result immediately
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} {name}: {status}")
        if message:
            print(f"   {message}")

    def summary(self):
        """Print summary of all results."""
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")

        print("\n" + "=" * 60)
        print(f"SUMMARY: {passed} passed, {failed} failed, {skipped} skipped")
        print("=" * 60)

        return failed == 0


results = TestResult()


# ============================================================================
# Clerk Authentication Tests
# ============================================================================

async def test_clerk_config():
    """Test Clerk configuration."""
    print("\n--- Clerk Configuration ---")

    from app.core.config import get_settings
    settings = get_settings()

    if not settings.clerk_publishable_key:
        results.add("Clerk publishable key", "FAIL", "CLERK_PUBLISHABLE_KEY not set")
        return False

    if not settings.clerk_secret_key:
        results.add("Clerk secret key", "FAIL", "CLERK_SECRET_KEY not set")
        return False

    results.add("Clerk publishable key", "PASS", f"Key starts with: {settings.clerk_publishable_key[:20]}...")
    results.add("Clerk secret key", "PASS", f"Key starts with: {settings.clerk_secret_key[:15]}...")

    # Test JWKS URL derivation
    jwks_url = settings.clerk_jwks_url
    if jwks_url:
        results.add("Clerk JWKS URL", "PASS", jwks_url)
    else:
        results.add("Clerk JWKS URL", "FAIL", "Could not derive JWKS URL from publishable key")
        return False

    return True


async def test_clerk_jwks():
    """Test Clerk JWKS endpoint."""
    print("\n--- Clerk JWKS Endpoint ---")

    from app.core.config import get_settings
    settings = get_settings()

    if not settings.clerk_jwks_url:
        results.add("Clerk JWKS fetch", "SKIP", "JWKS URL not available")
        return False

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(settings.clerk_jwks_url, timeout=10.0)

            if response.status_code == 200:
                jwks = response.json()
                keys = jwks.get("keys", [])
                results.add("Clerk JWKS fetch", "PASS", f"Retrieved {len(keys)} signing keys")
                return True
            else:
                results.add("Clerk JWKS fetch", "FAIL", f"HTTP {response.status_code}")
                return False
    except Exception as e:
        results.add("Clerk JWKS fetch", "FAIL", str(e))
        return False


async def test_clerk_api():
    """Test Clerk Backend API connectivity."""
    print("\n--- Clerk Backend API ---")

    from app.core.config import get_settings
    settings = get_settings()

    if not settings.clerk_secret_key:
        results.add("Clerk API", "SKIP", "Secret key not available")
        return False

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            # Just check if we can reach the API
            response = await client.get(
                "https://api.clerk.com/v1/users?limit=1",
                headers={
                    "Authorization": f"Bearer {settings.clerk_secret_key}",
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )

            if response.status_code == 200:
                users = response.json()
                results.add("Clerk API", "PASS", f"Connection OK, found {len(users)} users")
                return True
            elif response.status_code == 401:
                results.add("Clerk API", "FAIL", "Invalid secret key (401)")
                return False
            else:
                results.add("Clerk API", "FAIL", f"HTTP {response.status_code}: {response.text[:100]}")
                return False
    except Exception as e:
        results.add("Clerk API", "FAIL", str(e))
        return False


async def run_clerk_tests():
    """Run all Clerk tests."""
    print("\n" + "=" * 60)
    print("CLERK AUTHENTICATION TESTS")
    print("=" * 60)

    config_ok = await test_clerk_config()
    if not config_ok:
        print("Skipping remaining Clerk tests due to config issues")
        return

    await test_clerk_jwks()
    await test_clerk_api()


# ============================================================================
# R2 Storage Tests
# ============================================================================

async def test_r2_config():
    """Test R2 configuration."""
    print("\n--- R2 Configuration ---")

    from app.core.config import get_settings
    settings = get_settings()

    if not settings.r2_account_id:
        results.add("R2 account ID", "FAIL", "R2_ACCOUNT_ID not set")
        return False

    if not settings.r2_access_key:
        results.add("R2 access key", "FAIL", "R2_ACCESS_KEY_ID not set")
        return False

    if not settings.r2_secret_key:
        results.add("R2 secret key", "FAIL", "R2_SECRET_ACCESS_KEY not set")
        return False

    results.add("R2 account ID", "PASS", settings.r2_account_id)
    results.add("R2 access key", "PASS", f"Key starts with: {settings.r2_access_key[:10]}...")
    results.add("R2 bucket name", "PASS", settings.r2_bucket_name)
    results.add("R2 endpoint URL", "PASS", settings.r2_endpoint_url)

    return True


async def test_r2_connection():
    """Test R2 bucket connection."""
    print("\n--- R2 Connection ---")

    from app.services.r2_storage import get_r2_service

    r2 = get_r2_service()

    if not r2.is_available:
        results.add("R2 client init", "FAIL", r2._init_error or "Unknown error")
        return False

    results.add("R2 client init", "PASS", "Client initialized successfully")
    return True


async def test_r2_operations():
    """Test R2 CRUD operations."""
    print("\n--- R2 Operations ---")

    from app.services.r2_storage import get_r2_service

    r2 = get_r2_service()

    if not r2.is_available:
        results.add("R2 operations", "SKIP", "R2 not available")
        return False

    # Test data
    test_user_id = 999999
    test_activity_id = 999999
    test_data = b"Test FIT file data - " + datetime.now(timezone.utc).isoformat().encode()

    # Test upload
    try:
        upload_result = await r2.upload_fit(
            user_id=test_user_id,
            activity_id=test_activity_id,
            fit_data=test_data,
            compress=True
        )

        if upload_result.get("success"):
            results.add("R2 upload", "PASS",
                f"Key: {upload_result['key']}, "
                f"Compression: {upload_result['compression_ratio']:.1f}%")
        else:
            results.add("R2 upload", "FAIL", upload_result.get("error", "Unknown error"))
            return False
    except Exception as e:
        results.add("R2 upload", "FAIL", str(e))
        return False

    # Test download
    try:
        downloaded = await r2.download_fit(
            user_id=test_user_id,
            activity_id=test_activity_id,
            decompress=True
        )

        if downloaded and downloaded == test_data:
            results.add("R2 download", "PASS", f"Retrieved {len(downloaded)} bytes")
        else:
            results.add("R2 download", "FAIL", "Data mismatch or not found")
            return False
    except Exception as e:
        results.add("R2 download", "FAIL", str(e))
        return False

    # Test presigned URL
    try:
        presigned = r2.generate_presigned_download_url(
            user_id=test_user_id,
            activity_id=test_activity_id,
            expires_in=300
        )

        if presigned:
            results.add("R2 presigned URL", "PASS", f"URL generated: {presigned[:80]}...")
        else:
            results.add("R2 presigned URL", "FAIL", "Failed to generate URL")
    except Exception as e:
        results.add("R2 presigned URL", "FAIL", str(e))

    # Test delete (cleanup)
    try:
        deleted = await r2.delete_fit(user_id=test_user_id, activity_id=test_activity_id)

        if deleted:
            results.add("R2 delete", "PASS", "Test file cleaned up")
        else:
            results.add("R2 delete", "WARN", "Delete may have failed, check bucket")
    except Exception as e:
        results.add("R2 delete", "WARN", f"Delete error: {e}")

    # Test storage stats
    try:
        stats = await r2.get_storage_stats()

        if "error" not in stats:
            results.add("R2 storage stats", "PASS",
                f"Files: {stats['total_files']}, "
                f"Size: {stats['total_size_mb']:.2f} MB, "
                f"Free tier: {stats['free_tier_used_percent']:.1f}% used")
        else:
            results.add("R2 storage stats", "FAIL", stats.get("error"))
    except Exception as e:
        results.add("R2 storage stats", "FAIL", str(e))

    return True


async def run_r2_tests():
    """Run all R2 tests."""
    print("\n" + "=" * 60)
    print("CLOUDFLARE R2 STORAGE TESTS")
    print("=" * 60)

    config_ok = await test_r2_config()
    if not config_ok:
        print("Skipping remaining R2 tests due to config issues")
        return

    conn_ok = await test_r2_connection()
    if not conn_ok:
        print("Skipping R2 operations tests due to connection issues")
        return

    await test_r2_operations()


# ============================================================================
# Neon Database Tests
# ============================================================================

async def test_neon_config():
    """Test Neon configuration."""
    print("\n--- Neon Configuration ---")

    from app.core.config import get_settings
    settings = get_settings()

    if "neon.tech" not in settings.database_url:
        results.add("Neon database URL", "WARN",
            "DATABASE_URL does not contain 'neon.tech'. "
            "Testing generic PostgreSQL connection instead.")
        return True  # Continue with generic PostgreSQL test

    results.add("Neon database URL", "PASS",
        f"Using Neon: {settings.database_url.split('@')[1].split('/')[0] if '@' in settings.database_url else 'hidden'}")

    return True


async def test_neon_connection():
    """Test Neon database connection."""
    print("\n--- Neon Connection ---")

    from sqlalchemy import text
    from app.core.database import async_session_maker

    try:
        async with async_session_maker() as session:
            # Test basic query
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()

            results.add("Database connection", "PASS", f"PostgreSQL version: {version[:50]}...")

            # Test tables exist
            result = await session.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]

            if tables:
                results.add("Database tables", "PASS",
                    f"Found {len(tables)} tables: {', '.join(tables[:5])}...")
            else:
                results.add("Database tables", "WARN",
                    "No tables found. Run migrations: alembic upgrade head")

            return True

    except Exception as e:
        results.add("Database connection", "FAIL", str(e))
        return False


async def test_neon_models():
    """Test database models."""
    print("\n--- Database Models ---")

    from sqlalchemy import select
    from app.core.database import async_session_maker
    from app.models.user import User

    try:
        async with async_session_maker() as session:
            # Count users
            result = await session.execute(select(User))
            users = result.scalars().all()

            results.add("User model", "PASS", f"Found {len(users)} users in database")

            # Check for Clerk-enabled users
            clerk_users = [u for u in users if u.clerk_user_id]
            results.add("Clerk users", "PASS" if clerk_users else "INFO",
                f"{len(clerk_users)} users with Clerk authentication")

            return True

    except Exception as e:
        results.add("Database models", "FAIL", str(e))
        return False


async def run_neon_tests():
    """Run all Neon tests."""
    print("\n" + "=" * 60)
    print("NEON DATABASE TESTS")
    print("=" * 60)

    config_ok = await test_neon_config()
    if not config_ok:
        print("Skipping remaining Neon tests due to config issues")
        return

    conn_ok = await test_neon_connection()
    if not conn_ok:
        print("Skipping model tests due to connection issues")
        return

    await test_neon_models()


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run selected tests."""
    parser = argparse.ArgumentParser(description="Test cloud services connectivity")
    parser.add_argument("--clerk", action="store_true", help="Test Clerk authentication")
    parser.add_argument("--r2", action="store_true", help="Test Cloudflare R2 storage")
    parser.add_argument("--neon", action="store_true", help="Test Neon database")
    parser.add_argument("--all", action="store_true", help="Run all tests")

    args = parser.parse_args()

    # Default to all if no specific tests selected
    run_all = args.all or not (args.clerk or args.r2 or args.neon)

    print("=" * 60)
    print("CLOUD SERVICES INTEGRATION TESTS")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    if run_all or args.clerk:
        await run_clerk_tests()

    if run_all or args.r2:
        await run_r2_tests()

    if run_all or args.neon:
        await run_neon_tests()

    # Print summary
    success = results.summary()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
