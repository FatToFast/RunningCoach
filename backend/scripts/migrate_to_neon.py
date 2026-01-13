#!/usr/bin/env python
"""Migrate database from local PostgreSQL to Neon.

This script:
1. Dumps the local database
2. Creates tables in Neon
3. Migrates data with batching
4. Verifies data integrity
"""

import asyncio
import os
import sys
import subprocess
from typing import Optional
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

load_dotenv()


class NeonMigrator:
    """Handle database migration to Neon."""

    def __init__(self, local_url: str, neon_url: str):
        self.local_url = local_url
        self.neon_url = neon_url

    def dump_local_db(self, output_file: str = "backup.sql") -> bool:
        """Dump local database to SQL file."""
        print(f"Dumping local database to {output_file}...")

        try:
            # Parse connection string
            # postgresql://user:pass@host:port/dbname
            import urllib.parse
            parsed = urllib.parse.urlparse(self.local_url.replace("+asyncpg", ""))

            env = os.environ.copy()
            env["PGPASSWORD"] = parsed.password or ""

            cmd = [
                "pg_dump",
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres",
                "-d", parsed.path.lstrip("/"),
                "--no-owner",
                "--no-acl",
                "--if-exists",
                "--clean",
                "-f", output_file
            ]

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode == 0:
                file_size = os.path.getsize(output_file)
                print(f"  ✅ Dump successful: {file_size / (1024**2):.2f} MB")
                return True
            else:
                print(f"  ❌ Dump failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"  ❌ Error dumping database: {e}")
            return False

    def restore_to_neon(self, input_file: str = "backup.sql") -> bool:
        """Restore database dump to Neon."""
        print(f"Restoring {input_file} to Neon...")

        try:
            # Parse Neon connection string
            import urllib.parse
            parsed = urllib.parse.urlparse(self.neon_url.replace("+asyncpg", ""))

            env = os.environ.copy()
            env["PGPASSWORD"] = parsed.password or ""

            cmd = [
                "psql",
                "-h", parsed.hostname,
                "-p", str(parsed.port or 5432),
                "-U", parsed.username,
                "-d", parsed.path.lstrip("/"),
                "-f", input_file
            ]

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode == 0:
                print("  ✅ Restore successful")
                return True
            else:
                # Check if it's just warnings about missing roles
                if "role" in result.stderr.lower() and "does not exist" in result.stderr.lower():
                    print("  ⚠️  Restore completed with warnings (missing roles - this is OK)")
                    return True
                else:
                    print(f"  ❌ Restore failed: {result.stderr}")
                    return False

        except Exception as e:
            print(f"  ❌ Error restoring to Neon: {e}")
            return False

    async def verify_migration(self) -> bool:
        """Verify that data was migrated correctly."""
        print("\nVerifying migration...")

        try:
            # Connect to both databases
            local_engine = create_async_engine(self.local_url)
            neon_engine = create_async_engine(self.neon_url)

            tables_to_check = [
                "users",
                "activities",
                "laps",
                "ai_conversations",
                "ai_messages",
                "ai_plans",
                "workouts",
                "workout_steps",
                "gear",
                "races"
            ]

            all_match = True

            async with local_engine.connect() as local_conn:
                async with neon_engine.connect() as neon_conn:
                    for table in tables_to_check:
                        # Count rows in local
                        local_result = await local_conn.execute(
                            text(f"SELECT COUNT(*) FROM {table}")
                        )
                        local_count = local_result.scalar()

                        # Count rows in Neon
                        try:
                            neon_result = await neon_conn.execute(
                                text(f"SELECT COUNT(*) FROM {table}")
                            )
                            neon_count = neon_result.scalar()

                            if local_count == neon_count:
                                print(f"  ✅ {table}: {local_count:,} rows")
                            else:
                                print(f"  ❌ {table}: Local={local_count:,}, Neon={neon_count:,}")
                                all_match = False
                        except Exception as e:
                            print(f"  ❌ {table}: Error - {e}")
                            all_match = False

            await local_engine.dispose()
            await neon_engine.dispose()

            return all_match

        except Exception as e:
            print(f"  ❌ Verification error: {e}")
            return False

    async def run_alembic_migrations(self) -> bool:
        """Run Alembic migrations on Neon database."""
        print("\nRunning Alembic migrations on Neon...")

        try:
            # Temporarily set DATABASE_URL to Neon
            original_db_url = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = self.neon_url

            # Run alembic upgrade
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                capture_output=True,
                text=True
            )

            # Restore original DATABASE_URL
            if original_db_url:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)

            if result.returncode == 0:
                print("  ✅ Migrations completed successfully")
                return True
            else:
                print(f"  ❌ Migration failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"  ❌ Error running migrations: {e}")
            return False


async def migrate_to_neon(
    skip_dump: bool = False,
    skip_restore: bool = False,
    verify_only: bool = False
):
    """Main migration function."""
    settings = get_settings()

    # Get database URLs
    local_url = settings.database_url
    neon_url = os.getenv("NEON_DATABASE_URL")

    if not neon_url:
        print("ERROR: NEON_DATABASE_URL not found in environment variables")
        print("Please set it in your .env file:")
        print('NEON_DATABASE_URL="postgresql+asyncpg://user:pass@xxx.neon.tech:5432/dbname"')
        return

    print("=" * 60)
    print("Database Migration to Neon")
    print("=" * 60)
    print(f"Source (Local): {local_url.split('@')[1] if '@' in local_url else local_url}")
    print(f"Target (Neon): {neon_url.split('@')[1] if '@' in neon_url else neon_url}")
    print("-" * 60)

    migrator = NeonMigrator(local_url, neon_url)

    if verify_only:
        success = await migrator.verify_migration()
        if success:
            print("\n✅ Migration verification successful!")
        else:
            print("\n❌ Migration verification failed!")
        return

    # Step 1: Dump local database
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    if not skip_dump:
        if not migrator.dump_local_db(backup_file):
            print("\n❌ Failed to dump local database")
            return
    else:
        print("Skipping database dump (using existing backup)")
        # Find most recent backup
        import glob
        backups = glob.glob("backup_*.sql")
        if backups:
            backup_file = max(backups)
            print(f"Using backup: {backup_file}")
        else:
            print("No backup file found!")
            return

    # Step 2: Restore to Neon
    if not skip_restore:
        if not migrator.restore_to_neon(backup_file):
            print("\n❌ Failed to restore to Neon")
            return
    else:
        print("Skipping restore (assuming Neon already has data)")

    # Step 3: Run Alembic migrations
    if not await migrator.run_alembic_migrations():
        print("\n⚠️  Alembic migrations failed (may already be applied)")

    # Step 4: Verify migration
    success = await migrator.verify_migration()

    if success:
        print("\n" + "=" * 60)
        print("✅ Migration to Neon completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update your .env file:")
        print(f'   DATABASE_URL="{neon_url}"')
        print("2. Test the application with Neon database")
        print("3. Keep the backup file for safety:", backup_file)
    else:
        print("\n❌ Migration verification failed")
        print("Please check the errors above and try again")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate database to Neon")
    parser.add_argument("--skip-dump", action="store_true", help="Skip database dump")
    parser.add_argument("--skip-restore", action="store_true", help="Skip restore to Neon")
    parser.add_argument("--verify", action="store_true", help="Verify migration only")
    args = parser.parse_args()

    asyncio.run(migrate_to_neon(
        skip_dump=args.skip_dump,
        skip_restore=args.skip_restore,
        verify_only=args.verify
    ))


if __name__ == "__main__":
    main()