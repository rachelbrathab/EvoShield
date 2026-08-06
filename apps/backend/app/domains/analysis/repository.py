"""Analysis domain data access — the AnalysisRun aggregate.

Ownership is derived through the repository row (run → repository → owner),
so every public query joins `repositories` and filters by `owner_id`. The
internal `get`/`get_with_name` helpers are unscoped by design — they are used
only by the orchestrator's background task, which operates on run ids it
already validated against the requesting user.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.repository import Repository

_ACTIVE_STATUSES = (AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING)


class AnalysisRunRepository:
    """Persists and queries analysis runs belonging to one user's repositories."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Owner-scoped public queries ─────────────────────────────────────
    async def get_for_owner(
        self, owner_id: uuid.UUID, run_id: uuid.UUID
    ) -> tuple[AnalysisRun, str | None] | None:
        """Return (run, repository_full_name) or None when not owned/absent."""
        stmt = (
            select(AnalysisRun, Repository.full_name)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(
                AnalysisRun.id == run_id,
                Repository.owner_id == owner_id,
            )
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def list_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        repository_id: uuid.UUID | None = None,
        status: AnalysisRunStatus | None = None,
    ) -> tuple[list[tuple[AnalysisRun, str]], int]:
        """Return ((run, full_name) rows, total) newest first."""
        stmt = (
            select(AnalysisRun, Repository.full_name)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(Repository.owner_id == owner_id)
        )
        count_stmt = (
            select(func.count())
            .select_from(AnalysisRun)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(Repository.owner_id == owner_id)
        )

        if repository_id is not None:
            stmt = stmt.where(AnalysisRun.repository_id == repository_id)
            count_stmt = count_stmt.where(AnalysisRun.repository_id == repository_id)
        if status is not None:
            stmt = stmt.where(AnalysisRun.status == status)
            count_stmt = count_stmt.where(AnalysisRun.status == status)

        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = stmt.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows], total

    # ── Run lifecycle queries ───────────────────────────────────────────
    async def get_active_for_repository(self, repository_id: uuid.UUID) -> AnalysisRun | None:
        """Return the run currently queued/running for a repository, if any."""
        stmt = select(AnalysisRun).where(
            AnalysisRun.repository_id == repository_id,
            AnalysisRun.status.in_(_ACTIVE_STATUSES),
        )
        return (await self._session.execute(stmt)).scalars().first()

    # Unscoped by design — orchestrator-internal use only (see module doc).
    async def get(self, run_id: uuid.UUID) -> AnalysisRun | None:
        stmt = select(AnalysisRun).where(AnalysisRun.id == run_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_with_name(self, run_id: uuid.UUID) -> tuple[AnalysisRun, str | None] | None:
        """Unscoped (run, full_name) lookup for the orchestrator's task."""
        stmt = (
            select(AnalysisRun, Repository.full_name)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(AnalysisRun.id == run_id)
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    # ── Shared-model access (Repository aggregate) ──────────────────────
    async def get_repository_for_owner(
        self, owner_id: uuid.UUID, repository_id: uuid.UUID
    ) -> Repository | None:
        """Return the repository row only when the owner owns it."""
        stmt = select(Repository).where(
            Repository.id == repository_id,
            Repository.owner_id == owner_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
