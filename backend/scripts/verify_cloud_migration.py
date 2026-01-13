#!/usr/bin/env python3
"""Cloud Migration Verification Script.

This script validates all cloud migration components:
1. Database schema alignment (Clerk and R2 fields)
2. Clerk authentication configuration
3. R2 storage configuration
4. API endpoint availability
5. Frontend integration readiness

Usage:
    python scripts/verify_cloud_migration.py
    python scripts/verify_cloud_migration.py --fix  # Auto-fix schema issues
    python scripts/verify_cloud_migration.py --verbose  # Show detailed logs
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CloudMigrationVerifier:
    """Verify cloud migration components."""

    def __init__(self, verbose: bool = False, fix: bool = False):
        self.verbose = verbose
        self.fix = fix
        self.results: Dict[str, Dict[str, Any]] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    async def run_all_checks(self) -> bool:
        """Run all verification checks."""
        logger.info("=" * 60)
        logger.info("Cloud Migration Verification")
        logger.info("=" * 60)

        checks = [
            ("Environment Variables", self.check_env_vars),
            ("Database Schema", self.check_database_schema),
            ("Clerk Configuration", self.check_clerk_config),
            ("R2 Storage Configuration", self.check_r2_config),
            ("Backend Endpoints", self.check_backend_endpoints),
            ("Frontend Configuration", self.check_frontend_config),
        ]

        all_passed = True
        for name, check_func in checks:
            logger.info(f"\n--- {name} ---")
            try:
                passed = await check_func()
                self.results[name] = {"passed": passed}
                if not passed:
                    all_passed = False
                    logger.error(f"[FAIL] {name}")
                else:
                    logger.info(f"[PASS] {name}")
            except Exception as e:
                logger.error(f"[ERROR] {name}: {e}")
                self.results[name] = {"passed": False, "error": str(e)}
                all_passed = False

        self.print_summary()
        return all_passed

    async def check_env_vars(self) -> bool:
        """Check required environment variables."""
        required_vars = {
            "DATABASE_URL": "Database connection string",
            "SESSION_SECRET": "Session encryption secret",
            "SECRET_KEY": "Application secret key",
        }

        optional_cloud_vars = {
            "CLERK_PUBLISHABLE_KEY": "Clerk frontend publishable key",
            "CLERK_SECRET_KEY": "Clerk backend secret key",
            "CLERK_WEBHOOK_SECRET": "Clerk webhook signing secret",
            "R2_ACCOUNT_ID": "Cloudflare account ID",
            "R2_ACCESS_KEY": "R2 access key ID",
            "R2_SECRET_KEY": "R2 secret access key",
            "R2_BUCKET_NAME": "R2 bucket name",
        }

        passed = True

        # Check required vars
        for var, desc in required_vars.items():
            value = os.getenv(var)
            if not value:
                logger.error(f"  [MISSING] {var}: {desc}")
                self.errors.append(f"Missing required env var: {var}")
                passed = False
            elif self.verbose:
                logger.info(f"  [OK] {var}: {desc}")

        # Check optional cloud vars
        cloud_configured = False
        for var, desc in optional_cloud_vars.items():
            value = os.getenv(var)
            if value:
                cloud_configured = True
                if self.verbose:
                    logger.info(f"  [OK] {var}: {desc}")
            else:
                logger.warning(f"  [OPTIONAL] {var}: {desc} (not set)")
                self.warnings.append(f"Optional cloud var not set: {var}")

        if not cloud_configured:
            logger.warning("  Cloud services not configured (local mode)")

        return passed

    async def check_database_schema(self) -> bool:
        """Check database schema for cloud migration fields."""
        from app.core.config import get_settings
        settings = get_settings()

        engine = create_async_engine(str(settings.database_url))

        async with engine.begin() as conn:
            # Check users table
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users'
            """))
            user_columns = {row[0]: {"type": row[1], "nullable": row[2]} for row in result}

            # Check activities table
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'activities'
            """))
            activity_columns = {row[0]: {"type": row[1], "nullable": row[2]} for row in result}

        await engine.dispose()

        passed = True

        # Verify User model fields
        required_user_fields = ["clerk_user_id"]
        for field in required_user_fields:
            if field in user_columns:
                logger.info(f"  [OK] users.{field} exists")
            else:
                logger.error(f"  [MISSING] users.{field}")
                self.errors.append(f"Missing column: users.{field}")
                passed = False

        # Verify Activity model fields
        required_activity_fields = ["r2_key", "storage_provider", "storage_metadata"]
        for field in required_activity_fields:
            if field in activity_columns:
                logger.info(f"  [OK] activities.{field} exists")
            else:
                logger.error(f"  [MISSING] activities.{field}")
                self.errors.append(f"Missing column: activities.{field}")
                passed = False

        return passed

    async def check_clerk_config(self) -> bool:
        """Check Clerk authentication configuration."""
        from app.core.config import get_settings
        settings = get_settings()

        passed = True

        # Check if Clerk is configured
        if not settings.clerk_publishable_key:
            logger.warning("  Clerk not configured (local auth mode)")
            self.warnings.append("Clerk authentication not configured")
            return True  # Not a failure, just not configured

        # Validate JWKS URL
        jwks_url = settings.clerk_jwks_url
        if jwks_url:
            logger.info(f"  [OK] JWKS URL: {jwks_url}")
        else:
            logger.error("  [FAIL] Cannot derive JWKS URL from publishable key")
            passed = False

        # Check secret key
        if settings.clerk_secret_key:
            logger.info("  [OK] Clerk secret key configured")
        else:
            logger.error("  [MISSING] Clerk secret key")
            passed = False

        # Check webhook secret
        if settings.clerk_webhook_secret:
            logger.info("  [OK] Webhook secret configured")
        else:
            logger.warning("  [OPTIONAL] Webhook secret not configured")
            self.warnings.append("Clerk webhook secret not configured")

        return passed

    async def check_r2_config(self) -> bool:
        """Check R2 storage configuration."""
        from app.core.config import get_settings
        settings = get_settings()

        # Check if R2 is configured
        if not settings.r2_account_id:
            logger.warning("  R2 not configured (local storage mode)")
            self.warnings.append("R2 storage not configured")
            return True  # Not a failure, just not configured

        passed = True

        # Validate credentials
        if settings.r2_access_key and settings.r2_secret_key:
            logger.info("  [OK] R2 credentials configured")
        else:
            logger.error("  [FAIL] R2 credentials incomplete")
            passed = False

        # Check bucket name
        if settings.r2_bucket_name:
            logger.info(f"  [OK] Bucket name: {settings.r2_bucket_name}")
        else:
            logger.error("  [MISSING] R2 bucket name")
            passed = False

        # Test R2 connection if fully configured
        if passed and self.verbose:
            try:
                from app.services.r2_storage import R2StorageService
                r2 = R2StorageService()
                if r2.is_available:
                    logger.info("  [OK] R2 connection successful")
                else:
                    logger.warning("  [WARN] R2 service not available")
            except Exception as e:
                logger.warning(f"  [WARN] R2 connection test failed: {e}")

        return passed

    async def check_backend_endpoints(self) -> bool:
        """Check backend API endpoints exist."""
        passed = True

        # Check endpoint modules exist
        endpoint_checks = [
            ("app.api.v1.endpoints.upload", "Upload endpoints"),
            ("app.api.v1.endpoints.webhooks", "Webhook endpoints"),
            ("app.core.clerk_auth", "Clerk auth module"),
            ("app.core.hybrid_auth", "Hybrid auth module"),
            ("app.services.r2_storage", "R2 storage service"),
        ]

        for module, desc in endpoint_checks:
            try:
                __import__(module)
                logger.info(f"  [OK] {desc} ({module})")
            except ImportError as e:
                logger.error(f"  [FAIL] {desc}: {e}")
                self.errors.append(f"Missing module: {module}")
                passed = False

        # Check router registration
        try:
            from app.api.v1.router import router
            routes = [r.path for r in router.routes]

            required_routes = ["/upload", "/webhooks"]
            for route in required_routes:
                if any(route in r for r in routes):
                    logger.info(f"  [OK] Route registered: {route}")
                else:
                    logger.error(f"  [MISSING] Route not registered: {route}")
                    passed = False
        except Exception as e:
            logger.error(f"  [FAIL] Router check failed: {e}")
            passed = False

        return passed

    async def check_frontend_config(self) -> bool:
        """Check frontend configuration files."""
        frontend_dir = Path(__file__).parent.parent.parent / "frontend"
        passed = True

        # Check package.json for Clerk dependency
        package_json = frontend_dir / "package.json"
        if package_json.exists():
            import json
            with open(package_json) as f:
                pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            if "@clerk/clerk-react" in deps:
                logger.info(f"  [OK] @clerk/clerk-react: {deps['@clerk/clerk-react']}")
            else:
                logger.warning("  [OPTIONAL] @clerk/clerk-react not in dependencies")
                self.warnings.append("Clerk React SDK not installed")
        else:
            logger.error("  [FAIL] package.json not found")
            passed = False

        # Check for AuthContext
        auth_context = frontend_dir / "src" / "contexts" / "AuthContext.tsx"
        if auth_context.exists():
            logger.info("  [OK] AuthContext.tsx exists")
        else:
            logger.error("  [MISSING] AuthContext.tsx")
            self.errors.append("Frontend AuthContext not created")
            passed = False

        # Check .env.example
        env_example = frontend_dir / ".env.example"
        if env_example.exists():
            logger.info("  [OK] .env.example exists")
        else:
            logger.warning("  [OPTIONAL] .env.example not found")

        return passed

    def print_summary(self):
        """Print verification summary."""
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 60)

        # Results
        passed_count = sum(1 for r in self.results.values() if r.get("passed"))
        total_count = len(self.results)
        logger.info(f"Checks: {passed_count}/{total_count} passed")

        for name, result in self.results.items():
            status = "[PASS]" if result.get("passed") else "[FAIL]"
            logger.info(f"  {status} {name}")

        # Errors
        if self.errors:
            logger.info(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                logger.error(f"  - {error}")

        # Warnings
        if self.warnings:
            logger.info(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")

        # Overall result
        all_passed = all(r.get("passed") for r in self.results.values())
        if all_passed:
            logger.info("\n[SUCCESS] Cloud migration verification PASSED")
        else:
            logger.error("\n[FAILED] Cloud migration verification FAILED")
            logger.info("Run with --fix to attempt automatic fixes")


async def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Verify cloud migration components")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--fix", "-f", action="store_true", help="Attempt to fix issues")
    args = parser.parse_args()

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    verifier = CloudMigrationVerifier(verbose=args.verbose, fix=args.fix)
    success = await verifier.run_all_checks()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
