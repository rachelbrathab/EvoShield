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
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

_engine_kwargs: dict[str, Any] = {}
if _settings.environment == "test":
    # Tests run in several distinct event loops (conftest's asyncio.run()
    # schema reset, TestClient's portal loop, pytest-asyncio) while sharing
    # one module-level engine. asyncpg connections are bound to the loop they
    # were created on, so a persistent queue pool hands a connection from one
    # test's loop to the next test's loop and raises
    # "got Future attached to a different loop" on Postgres (SQLite is immune:
    # aiosqlite runs each connection on its own thread). NullPool opens and
    # closes a connection per checkout, so nothing is ever reused across
    # loops — and pool_pre_ping is unnecessary (every checkout is fresh).
    # Production keeps the default pool with pre-ping.
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_pre_ping"] = True
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
