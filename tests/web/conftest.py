"""
Pytest fixtures for Sleep Scoring Web API tests.

Provides test client, test database, and test user fixtures.
Uses httpx for async testing with FastAPI.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sleep_scoring_web.db.models import Base, User
from sleep_scoring_web.main import app

# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine using in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session_maker(test_engine):
    """Create a session maker for the test database."""
    return async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture(scope="function")
async def test_session(test_session_maker) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async with test_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def setup_db(test_session_maker):
    """Override the database session dependency and set up test users."""
    from sleep_scoring_web.api.auth import get_password_hash
    from sleep_scoring_web.api.deps import get_db

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Create test users
    async with test_session_maker() as session:
        admin_user = User(
            email="admin@test.local",
            username="testadmin",
            hashed_password=get_password_hash("testpass123"),
            role="admin",
            is_active=True,
        )
        annotator_user = User(
            email="annotator@test.local",
            username="testannotator",
            hashed_password=get_password_hash("testpass123"),
            role="annotator",
            is_active=True,
        )
        session.add(admin_user)
        session.add(annotator_user)
        await session.commit()

    yield

    app.dependency_overrides.clear()


# =============================================================================
# Client Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def client(setup_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Auth Token Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def admin_token(client: AsyncClient) -> str:
    """Get JWT token for admin user."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testadmin", "password": "testpass123"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def annotator_token(client: AsyncClient) -> str:
    """Get JWT token for annotator user."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testannotator", "password": "testpass123"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def admin_auth_headers(admin_token: str) -> dict[str, str]:
    """Get auth headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture(scope="function")
async def annotator_auth_headers(annotator_token: str) -> dict[str, str]:
    """Get auth headers for annotator user."""
    return {"Authorization": f"Bearer {annotator_token}"}


# =============================================================================
# Legacy User Fixtures (for auth tests that need explicit user object)
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def test_admin_user(setup_db, test_session_maker) -> User:
    """Get the test admin user."""
    from sqlalchemy import select

    async with test_session_maker() as session:
        result = await session.execute(select(User).where(User.username == "testadmin"))
        return result.scalar_one()


@pytest_asyncio.fixture(scope="function")
async def test_annotator_user(setup_db, test_session_maker) -> User:
    """Get the test annotator user."""
    from sqlalchemy import select

    async with test_session_maker() as session:
        result = await session.execute(select(User).where(User.username == "testannotator"))
        return result.scalar_one()


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def sample_csv_content() -> str:
    """
    Generate sample CSV content for testing.

    Mimics ActiGraph format with 10 header rows followed by data.
    The loader skips the first 10 rows by default.
    """
    import datetime

    # ActiGraph-style header rows (10 rows)
    lines = [
        "------------ Data File Created By ActiGraph GT3X+ ActiLife v6.13.4 Firmware v3.2.1 date format M/d/yyyy Filter Normal -----------",
        "Serial Number: NEO1F00000000",
        "Start Time 00:00:00",
        "Start Date 1/1/2024",
        "Epoch Period (hh:mm:ss) 00:01:00",
        "Download Time 12:00:00",
        "Download Date 1/2/2024",
        "Current Memory Address: 0",
        "Current Battery Voltage: 4.20     Mode = 12",
        "--------------------------------------------------",
        # Row 11 is the actual header (skipped rows = 10)
        "Date,Time,Axis1,Axis2,Axis3,Vector Magnitude",
    ]

    # Generate 100 rows of sample data
    base_time = datetime.datetime(2024, 1, 1, 0, 0, 0)
    for i in range(100):
        ts = base_time + datetime.timedelta(seconds=60 * i)
        date_str = ts.strftime("%m/%d/%Y")
        time_str = ts.strftime("%H:%M:%S")
        # Axis1 = Y (activity), Axis2 = X, Axis3 = Z
        lines.append(f"{date_str},{time_str},{(i * 2) % 150},{i % 100},{(i * 3) % 200},{i * 4}")

    return "\n".join(lines)


@pytest.fixture
def temp_csv_file(tmp_path: Path, sample_csv_content: str) -> Path:
    """Create a temporary CSV file for testing."""
    csv_path = tmp_path / "test_data.csv"
    csv_path.write_text(sample_csv_content)
    return csv_path
