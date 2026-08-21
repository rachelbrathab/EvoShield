"""FindingStatusRepository — data access for finding lifecycle status.

Each method enforces ownership through the chain:
    finding_status → finding → analysis_run → repository → owner
"""

import uuid
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.remediation.enums import FindingStatus
from app.models.analysis_run import AnalysisRun
from app.models.finding import Finding
from app.models.finding_status import FindingStatusRecord
from app.models.repository import Repository


def _get_status_value(record: FindingStatusRecord) -> str:
    """Safely extract the status value from a FindingStatusRecord."""
    val = record.status
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


class FindingStatusRepository:
    """Persists and queries finding lifecycle status records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_none(self, finding_id: uuid.UUID) -> FindingStatusRecord | None:
        """Return the status record for a finding, or None (meaning OPEN)."""
        stmt = select(FindingStatusRecord).where(FindingStatusRecord.finding_id == finding_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_for_owner(
        self, owner_id: uuid.UUID, finding_id: uuid.UUID
    ) -> FindingStatusRecord | None:
        """Return status only when the owner owns the parent repository."""
        stmt = (
            select(FindingStatusRecord)
            .join(Finding, FindingStatusRecord.finding_id == Finding.id)
            .join(AnalysisRun, Finding.analysis_run_id == AnalysisRun.id)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(
                FindingStatusRecord.finding_id == finding_id,
                Repository.owner_id == owner_id,
            )
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def set_status(
        self,
        finding_id: uuid.UUID,
        status: FindingStatus,
        *,
        user_id: uuid.UUID | None = None,
        note: str | None = None,
    ) -> FindingStatusRecord:
        """Create or update the status for a finding."""
        existing = await self.get_or_none(finding_id)
        if existing is not None:
            existing.status = status  # type: ignore[assignment]
            existing.set_by_user_id = user_id  # type: ignore[assignment]
            if note is not None:
                existing.note = note[:1024]
            await self._session.flush()
            return existing

        record = FindingStatusRecord(
            finding_id=finding_id,
            status=status,
            set_by_user_id=user_id,
            note=note[:1024] if note else None,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_status_for_analysis(
        self, analysis_id: uuid.UUID
    ) -> dict[uuid.UUID, FindingStatusRecord]:
        """Return a map of finding_id → status record for an analysis run."""
        stmt = (
            select(FindingStatusRecord)
            .join(Finding, FindingStatusRecord.finding_id == Finding.id)
            .where(Finding.analysis_run_id == analysis_id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {r.finding_id: r for r in rows}

    async def count_by_status_for_analysis(self, analysis_id: uuid.UUID) -> dict[str, int]:
        """Count findings by status for an analysis run.

        Findings without a status record are counted as OPEN.
        """
        status_map = await self.list_status_for_analysis(analysis_id)

        # Count all findings for the analysis.
        stmt = (
            select(func.count()).select_from(Finding).where(Finding.analysis_run_id == analysis_id)
        )
        total = int((await self._session.execute(stmt)).scalar_one())

        # Count statuses.
        counts: dict[str, int] = {s.value: 0 for s in FindingStatus}
        for status_record in status_map.values():
            counts[_get_status_value(status_record)] += 1

        # Uncounted findings default to OPEN.
        counted = sum(counts.values())
        counts[FindingStatus.OPEN.value] += total - counted

        return counts


def get_status_from_map(
    status_map: Mapping[uuid.UUID, FindingStatusRecord],
    finding_id: uuid.UUID,
) -> str:
    """Extract status value from a status map, defaulting to OPEN."""
    record = status_map.get(finding_id)
    if record is not None:
        return _get_status_value(record)
    return FindingStatus.OPEN.value
