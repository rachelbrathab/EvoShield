"""Github domain data access — the Repository aggregate.

All queries are scoped to an owner (the authenticated user) so repository
rows are never visible across accounts. Listing supports the search, filter,
sort and pagination contract of `GET /repositories`.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import AnalysisStatus, Repository

# Sort keys accepted by the API, mapped to ORM columns. Whitelist only —
# user input never reaches SQLAlchemy as a raw column expression. Values are
# `Any` because the ORM attribute generics (str/int/datetime) don't unify
# into a single ColumnElement generic; the keys are Literal-whitelisted at
# the router, so no user input can reach this dict.
SORT_COLUMNS: dict[str, Any] = {
    "name": Repository.name,
    "stars": Repository.stars,
    "forks": Repository.forks,
    "language": Repository.language,
    "size_kb": Repository.size_kb,
    "pushed_at": Repository.pushed_at,
    "created_at": Repository.created_at,
    "updated_at": Repository.updated_at,
}


class RepositoryRepository:
    """Persists and queries repositories belonging to one user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_owner(
        self, owner_id: uuid.UUID, repository_id: uuid.UUID
    ) -> Repository | None:
        stmt = select(Repository).where(
            Repository.id == repository_id,
            Repository.owner_id == owner_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_full_name(self, owner_id: uuid.UUID, full_name: str) -> Repository | None:
        stmt = select(Repository).where(
            Repository.owner_id == owner_id,
            Repository.full_name == full_name,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        owner_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        language: str | None,
        visibility: str | None,
        status: AnalysisStatus | None,
        archived: bool | None,
        disabled: bool | None,
        imported_after: datetime | None,
        sort: str,
        order: str,
    ) -> tuple[Sequence[Repository], int]:
        """Return (rows, total_count) honoring every list filter."""
        stmt = select(Repository).where(Repository.owner_id == owner_id)
        count_stmt = (
            select(func.count()).select_from(Repository).where(Repository.owner_id == owner_id)
        )

        if search:
            needle = f"%{search}%"
            match = or_(
                Repository.name.ilike(needle),
                Repository.full_name.ilike(needle),
                Repository.description.ilike(needle),
            )
            stmt = stmt.where(match)
            count_stmt = count_stmt.where(match)
        if language:
            stmt = stmt.where(Repository.language == language)
            count_stmt = count_stmt.where(Repository.language == language)
        if visibility in ("public", "private"):
            is_private = visibility == "private"
            stmt = stmt.where(Repository.is_private == is_private)
            count_stmt = count_stmt.where(Repository.is_private == is_private)
        if status is not None:
            stmt = stmt.where(Repository.analysis_status == status)
            count_stmt = count_stmt.where(Repository.analysis_status == status)
        if archived is not None:
            stmt = stmt.where(Repository.archived == archived)
            count_stmt = count_stmt.where(Repository.archived == archived)
        if disabled is not None:
            stmt = stmt.where(Repository.disabled == disabled)
            count_stmt = count_stmt.where(Repository.disabled == disabled)
        if imported_after is not None:
            # "Imported" is interpreted as import recency: when EvoShield
            # started tracking the repository (`created_at`).
            stmt = stmt.where(Repository.created_at >= imported_after)
            count_stmt = count_stmt.where(Repository.created_at >= imported_after)

        total = int((await self._session.execute(count_stmt)).scalar_one())

        column = SORT_COLUMNS.get(sort, Repository.updated_at)
        ordered = column.desc() if order == "desc" else column.asc()
        # Secondary key keeps pagination deterministic on ties (e.g. two
        # repos created in the same second).
        stmt = stmt.order_by(ordered, Repository.id.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, total

    async def delete(self, repository: Repository) -> None:
        await self._session.delete(repository)
        await self._session.flush()
