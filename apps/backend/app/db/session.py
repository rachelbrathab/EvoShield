"""Async SQLAlchemy engine and session factory.

Postgres (asyncpg) is the primary target — Supabase-managed in production.
SQLite (aiosqlite) is supported as a zero-dependency local dev fallback.
See docs/adr/0001-database-layer.md for the rationale.
"""

from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()

_engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
if _settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Fail connectivity checks quickly instead of hanging on a dead database.
    _engine_kwargs["connect_args"] = {"timeout": 5}

engine: AsyncEngine = create_async_engine(_settings.database_url, **_engine_kwargs)

session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
