#!/usr/bin/env python3
"""
Schema drift detection script.

Compares SQLAlchemy models with actual database schema and reports differences.
Run after git pull to detect missing columns before starting the server.

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/check_schema.py
    python scripts/check_schema.py --fix  # Auto-fix missing columns
"""
import asyncio
import argparse
import sys
from sqlalchemy import text, inspect
from sqlalchemy.orm import class_mapper

# Add parent to path for imports
sys.path.insert(0, ".")

from app.core.database import async_session_maker, engine
from app.models.activity import Activity, ActivityLap, ActivitySample, ActivityMetric
from app.models.gear import Gear, ActivityGear
from app.models.garmin import GarminSession, GarminRawEvent, GarminRawFile, GarminSyncState
from app.models.health import Sleep, HRRecord, HealthMetric, HeartRateZone, BodyComposition, FitnessMetricDaily
from app.models.user import User


# Map Python types to PostgreSQL types
TYPE_MAP = {
    "Integer": ["integer", "bigint"],
    "BigInteger": ["bigint"],
    "String": ["character varying", "varchar", "text"],
    "Text": ["text", "character varying"],
    "Boolean": ["boolean"],
    "DateTime": ["timestamp with time zone", "timestamp without time zone"],
    "Date": ["date"],
    "Float": ["double precision", "real", "numeric"],
    "JSON": ["jsonb", "json"],
    "JSONB": ["jsonb"],
    "LargeBinary": ["bytea"],
}


async def get_db_columns(table_name: str) -> dict[str, str]:
    """Get columns from database."""
    async with async_session_maker() as session:
        result = await session.execute(text(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """))
        return {row[0]: row[1] for row in result.fetchall()}


def get_model_columns(model_class) -> dict[str, str]:
    """Get columns from SQLAlchemy model."""
    mapper = class_mapper(model_class)
    columns = {}
    for column in mapper.columns:
        col_type = type(column.type).__name__
        columns[column.name] = col_type
    return columns


async def check_table(model_class, fix: bool = False) -> list[str]:
    """Check a single table for schema drift."""
    table_name = model_class.__tablename__
    issues = []

    try:
        db_columns = await get_db_columns(table_name)
    except Exception as e:
        return [f"  ERROR: Could not read table {table_name}: {e}"]

    if not db_columns:
        return [f"  ERROR: Table {table_name} does not exist"]

    model_columns = get_model_columns(model_class)

    # Find missing columns
    missing = set(model_columns.keys()) - set(db_columns.keys())

    if missing:
        for col in missing:
            col_type = model_columns[col]
            pg_type = get_pg_type(col_type)
            issues.append(f"  MISSING: {table_name}.{col} ({col_type} -> {pg_type})")

            if fix:
                await add_column(table_name, col, pg_type)
                issues[-1] += " [FIXED]"

    # Find extra columns (in DB but not in model)
    extra = set(db_columns.keys()) - set(model_columns.keys())
    if extra:
        for col in extra:
            issues.append(f"  EXTRA: {table_name}.{col} (in DB but not in model)")

    return issues


def get_pg_type(sqlalchemy_type: str) -> str:
    """Convert SQLAlchemy type to PostgreSQL type."""
    mapping = {
        "Integer": "INTEGER",
        "BigInteger": "BIGINT",
        "String": "VARCHAR(255)",
        "Text": "TEXT",
        "Boolean": "BOOLEAN DEFAULT FALSE",
        "DateTime": "TIMESTAMPTZ",
        "Date": "DATE",
        "Float": "DOUBLE PRECISION",
        "JSON": "JSONB",
        "JSONB": "JSONB",
    }
    return mapping.get(sqlalchemy_type, "TEXT")


async def add_column(table_name: str, column_name: str, pg_type: str):
    """Add a missing column to the database."""
    async with async_session_maker() as session:
        await session.execute(text(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {pg_type}"
        ))
        await session.commit()


async def main(fix: bool = False):
    """Main entry point."""
    print("=" * 60)
    print("Schema Drift Detection")
    print("=" * 60)

    if fix:
        print("Mode: FIX (will add missing columns)")
    else:
        print("Mode: CHECK ONLY (use --fix to auto-fix)")
    print()

    models = [
        User,
        Activity,
        ActivityLap,
        ActivitySample,
        ActivityMetric,
        Gear,
        ActivityGear,
        GarminSession,
        GarminRawEvent,
        GarminRawFile,
        GarminSyncState,
        Sleep,
        HRRecord,
        HealthMetric,
        HeartRateZone,
        BodyComposition,
        FitnessMetricDaily,
    ]

    all_issues = []

    for model in models:
        table_name = model.__tablename__
        print(f"Checking {table_name}...")
        issues = await check_table(model, fix=fix)

        if issues:
            all_issues.extend(issues)
            for issue in issues:
                print(issue)
        else:
            print(f"  OK")

    print()
    print("=" * 60)

    if all_issues:
        missing_count = sum(1 for i in all_issues if "MISSING" in i)
        extra_count = sum(1 for i in all_issues if "EXTRA" in i)

        print(f"Found {missing_count} missing columns, {extra_count} extra columns")

        if not fix and missing_count > 0:
            print()
            print("Run with --fix to automatically add missing columns:")
            print("  python scripts/check_schema.py --fix")

        return 1
    else:
        print("All tables match models!")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check for schema drift")
    parser.add_argument("--fix", action="store_true", help="Auto-fix missing columns")
    args = parser.parse_args()

    exit_code = asyncio.run(main(fix=args.fix))
    sys.exit(exit_code)
