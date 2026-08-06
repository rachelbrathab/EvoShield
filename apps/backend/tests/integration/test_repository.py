"""Integration tests for the Repository aggregate + RepositoryRead contract.

Sprint 3 preparation: proves a repository row persists, defaults to
NOT_ANALYZED, can be transitioned through the analysis lifecycle exactly as
the Sprint 4 pipeline will, and serializes through the `RepositoryRead`
schema with the analysis status as a plain string.
"""

import asyncio
import uuid
from typing import Any, cast

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.session import session_factory
from app.domains.github.schemas import RepositoryRead
from app.models.repository import AnalysisStatus, Repository
from app.models.user import User


async def _new_user(session, email: str | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email or f"repo-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Repo Tester",
        auth_provider="local",
    )
    session.add(user)
    await session.flush()
    return user


def test_repository_defaults_and_status_lifecycle() -> None:
    """Fresh repositories start NOT_ANALYZED; the pipeline can transition them."""

    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)

            repo = Repository(
                owner_id=user.id,
                provider="github",
                name="evoshield",
                full_name="evoshield/evoshield",
            )
            session.add(repo)
            await session.flush()

            # Defaults: not analyzed, no run info yet.
            assert repo.analysis_status is AnalysisStatus.NOT_ANALYZED
            assert repo.last_analysis_at is None
            assert repo.last_analysis_job_id is None

            # Contract serialization of the default state.
            read = RepositoryRead.model_validate(repo)
            assert read.analysis_status is AnalysisStatus.NOT_ANALYZED
            assert read.full_name == "evoshield/evoshield"
            assert read.model_dump(mode="json")["analysis_status"] == "not_analyzed"

            # The exact transitions the Sprint 4 pipeline will perform.
            repo.analysis_status = AnalysisStatus.QUEUED
            repo.last_analysis_job_id = "job-abc123"
            await session.flush()
            assert repo.analysis_status is AnalysisStatus.QUEUED

            await session.commit()

        # Persisted state round-trips through a fresh session + schema.
        async with session_factory() as session:
            stored = (await session.execute(select(Repository))).scalar_one()
            assert stored.analysis_status is AnalysisStatus.QUEUED
            assert stored.last_analysis_job_id == "job-abc123"
            read = RepositoryRead.model_validate(stored)
            assert read.analysis_status is AnalysisStatus.QUEUED
            assert read.last_analysis_job_id == "job-abc123"

    asyncio.run(scenario())


def test_invalid_status_value_rejected_at_model_boundary() -> None:
    """Free-form strings cannot be assigned to the enum column."""

    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)
            repo = Repository(
                owner_id=user.id,
                name="evoshield",
                full_name="evoshield/evoshield",
            )
            session.add(repo)
            await session.flush()
            # Deliberately bypasses the typed setter (cast(Any, ...)) to prove
            # the enum column rejects free-form strings at the model boundary
            # (StatementError wrapping a LookupError from the bind processor).
            repo.analysis_status = cast(Any, "running-something-else")
            with pytest.raises(StatementError) as excinfo:
                await session.flush()
            assert isinstance(excinfo.value.__cause__, LookupError)

    asyncio.run(scenario())


def test_duplicate_full_name_rejected_per_owner() -> None:
    """(owner_id, full_name) is the natural key — no duplicate rows."""

    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)
            session.add_all(
                [
                    Repository(owner_id=user.id, name="a", full_name="owner/a"),
                    Repository(owner_id=user.id, name="a", full_name="owner/a"),
                ]
            )
            with pytest.raises(IntegrityError):
                await session.commit()

    asyncio.run(scenario())
