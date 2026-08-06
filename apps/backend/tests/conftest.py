"""Shared test fixtures.

Default test database is a throwaway SQLite file — hermetic, no external
services. When CI sets DATABASE_URL to the Postgres service container
(see .github/workflows/ci.yml), tests exercise the real production dialect.

Environment variables MUST be set before the application package is imported,
because settings and the engine are built at import time.
"""

import os
from collections.abc import Iterator

# setdefault (not assignment) so an explicit DATABASE_URL from CI/Postgres
# service container is respected; SQLite is only the local default.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.db.session import engine
from app.main import app
from app.models import Base


@pytest.fixture(autouse=True)
def _database_schema() -> Iterator[None]:
    """Reset the test schema before every test.

    Uses the same metadata Alembic manages, so tests run against a schema
    identical to `alembic upgrade head`. Per-test reset keeps tests fully
    isolated — no row leakage between tests (e.g. duplicate-email cases).
    """
    import asyncio

    async def _reset() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())
    yield


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """A TestClient bound to the configured FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client
