"""Pytest configuration and fixtures for backend tests."""

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, StaticPool, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.session import create_session, get_session
from app.main import app as main_app


# -------------------------------------------------------------------------
# SQLite JSONB Compatibility - Convert JSONB to JSON for SQLite
# -------------------------------------------------------------------------

@event.listens_for(Base.metadata, "before_create")
def _convert_jsonb_to_json(target, connection, **kw):
    """Convert JSONB columns to JSON for SQLite compatibility."""
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()

# Import all models to ensure they're registered with Base
from app.models import (
    User,
    GarminSession,
    GarminSyncState,
    Activity,
    ActivityMetric,
    Sleep,
    HRRecord,
    HealthMetric,
    FitnessMetricDaily,
    Workout,
    WorkoutSchedule,
    AnalyticsSummary,
)
from app.models.gear import Gear, ActivityGear
from app.models.strava import StravaSession, StravaActivityMap, StravaSyncState


# -------------------------------------------------------------------------
# Database Fixtures
# -------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    """Create an async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    """Create a FastAPI app instance with test database."""

    async def override_get_db():
        yield db_session

    main_app.dependency_overrides[get_db] = override_get_db
    yield main_app
    main_app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# -------------------------------------------------------------------------
# User Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    from app.core.security import get_password_hash

    user = User(
        email="test@example.com",
        password_hash=get_password_hash("testpassword123"),
        display_name="Test User",
        timezone="Asia/Seoul",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_client(
    app: FastAPI,
    test_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated HTTP client."""
    # Mock session storage
    session_store = {}

    async def mock_create_session(user_id: int, user_data: dict) -> str:
        session_id = f"test_session_{user_id}"
        session_store[session_id] = {"user_id": user_id, **user_data}
        return session_id

    async def mock_get_session(session_id: str) -> dict | None:
        return session_store.get(session_id)

    async def mock_delete_session(session_id: str) -> None:
        session_store.pop(session_id, None)

    # Patch at the location where it's imported, not where it's defined
    with patch("app.api.v1.endpoints.auth.get_session", mock_get_session):
        with patch("app.api.v1.endpoints.auth.create_session", mock_create_session):
            with patch("app.api.v1.endpoints.auth.delete_session", mock_delete_session):
                # Create session for test user
                session_id = await mock_create_session(
                    test_user.id,
                    {"email": test_user.email, "display_name": test_user.display_name},
                )

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"session_id": session_id},
                ) as ac:
                    yield ac


# -------------------------------------------------------------------------
# Garmin Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
def mock_garmin_adapter():
    """Create a mock Garmin adapter."""
    with patch("app.api.v1.endpoints.auth.GarminConnectAdapter") as mock_class:
        mock_adapter = MagicMock()
        mock_adapter.login = MagicMock(return_value=True)
        mock_adapter.login_with_session = MagicMock(return_value=True)
        mock_adapter.get_session_data = MagicMock(
            return_value={"oauth_token": "test_token", "session_cookie": "test_cookie"}
        )
        mock_class.return_value = mock_adapter
        yield mock_adapter


# -------------------------------------------------------------------------
# Health Data Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
async def sample_activities(db_session: AsyncSession, test_user: User):
    """Create sample activities for testing."""
    from app.models.activity import Activity

    # Use current date for activities so they appear in API queries
    today = datetime.now(timezone.utc)
    activities = []
    for i in range(5):
        activity = Activity(
            user_id=test_user.id,
            garmin_id=1000 + i,
            activity_type="running",
            name=f"Test Run {i + 1}",
            start_time=today - timedelta(days=i),  # Activities from past 5 days
            duration_seconds=3600,
            distance_meters=10000,
            avg_hr=150,
            calories=500,
        )
        activities.append(activity)
        db_session.add(activity)

    await db_session.commit()
    return activities


@pytest.fixture
async def sample_health_data(db_session: AsyncSession, test_user: User):
    """Create sample health data for testing."""
    from app.models.health import FitnessMetricDaily, HealthMetric, HRRecord, Sleep

    # Use current date for health data
    today = date.today()
    now = datetime.now(timezone.utc)

    # Sleep record
    sleep = Sleep(
        user_id=test_user.id,
        date=today,
        duration_seconds=27000,  # 7.5 hours
        score=85,
    )
    db_session.add(sleep)

    # HR record
    hr_record = HRRecord(
        user_id=test_user.id,
        date=today,  # Required field for unique constraint
        start_time=now,
        resting_hr=52,
        avg_hr=65,
        max_hr=180,
    )
    db_session.add(hr_record)

    # Health metrics (body battery, vo2max)
    body_battery = HealthMetric(
        user_id=test_user.id,
        metric_type="body_battery",
        metric_time=now,
        value=78,
        unit="percent",
    )
    db_session.add(body_battery)

    vo2max = HealthMetric(
        user_id=test_user.id,
        metric_type="vo2max",
        metric_time=now,
        value=52.4,
        unit="ml/kg/min",
    )
    db_session.add(vo2max)

    # Fitness metrics
    fitness = FitnessMetricDaily(
        user_id=test_user.id,
        date=today,
        ctl=58.2,
        atl=72.5,
        tsb=-14.3,
    )
    db_session.add(fitness)

    await db_session.commit()

    return {
        "sleep": sleep,
        "hr_record": hr_record,
        "body_battery": body_battery,
        "vo2max": vo2max,
        "fitness": fitness,
    }
