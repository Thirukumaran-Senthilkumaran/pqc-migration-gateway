"""SQLAlchemy async setup."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def init_db() -> None:
    """Create tables if they do not exist (lightweight migration).

    Also performs additive column migrations for gateway_sessions so the new
    crypto-policy columns appear in databases created by older builds.
    """
    # Local import keeps SQLAlchemy from seeing models before Base is ready.
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # additive migrations
        await _ensure_columns(
            conn,
            "gateway_sessions",
            {
                "crypto_suite": "VARCHAR(32) DEFAULT 'pqc-full' NOT NULL",
                "scope":        "VARCHAR(16) DEFAULT 'lan-wan' NOT NULL",
                "suite_history": "TEXT",
            },
        )


async def _ensure_columns(conn, table: str, columns: dict[str, str]) -> None:
    """Best-effort add-missing-column migration for SQLite."""
    from sqlalchemy import text

    res = await conn.execute(text(f"PRAGMA table_info({table})"))
    existing = {row[1] for row in res.fetchall()}
    for col, ddl in columns.items():
        if col not in existing:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
            except Exception:
                pass


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context manager for one DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with AsyncSessionLocal() as session:
        yield session
