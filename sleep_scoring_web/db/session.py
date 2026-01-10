"""
Database session management.

Provides async SQLAlchemy engine and session factory using db-toolkit.
"""

from __future__ import annotations

from db_toolkit import create_engine, create_get_db, create_session_maker
from sqlalchemy.ext.asyncio import create_async_engine as sa_create_async_engine

from sleep_scoring_web.config import settings

# Configure engine based on database type
if settings.use_sqlite:
    # SQLite configuration (for development)
    # db-toolkit handles SQLite specially (no pooling)
    async_engine = sa_create_async_engine(
        settings.database_url,
        echo=settings.sql_echo,
    )
    async_session_maker = create_session_maker(async_engine)
else:
    # PostgreSQL configuration (production)
    # Use db-toolkit for standardized connection pooling
    async_engine = create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        echo=settings.sql_echo,
    )
    async_session_maker = create_session_maker(async_engine)

# Create get_db dependency using db-toolkit
get_async_session = create_get_db(async_session_maker)


async def init_db() -> None:
    """Initialize database tables."""
    from sleep_scoring_web.db.models import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drop all database tables (use with caution)."""
    from sleep_scoring_web.db.models import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
