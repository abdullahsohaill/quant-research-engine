"""
Quant Research Engine — Database Connection

Async SQLAlchemy engine and session management for PostgreSQL.
Uses connection pooling optimized for Docker deployment.
"""

import logging
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings
from backend.data.models import Base

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Async Engine (for FastAPI) ────────────────────────────────
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync Engine (for seeding & MCP servers) ───────────────────
sync_engine = create_engine(
    settings.sync_database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(bind=sync_engine)


async def init_db():
    """Create all database tables if they don't exist."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified successfully.")


def init_db_sync():
    """Create all database tables synchronously (for scripts)."""
    Base.metadata.create_all(bind=sync_engine)
    logger.info("Database tables created/verified successfully (sync).")


async def get_db() -> AsyncSession:
    """Dependency injector for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_db():
    """Get a synchronous database session."""
    session = SyncSessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise
