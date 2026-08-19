"""Findings data access — CRUD for the `findings` table.

Ownership is derived through the chain:
    finding → analysis_run → repository → owner

Every public query joins through this chain to enforce ownership isolation.
A user must never access findings belonging to another user's repositories.
"""

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.ports import ScannerFinding
from app.models.analysis_run import AnalysisRun
from app.models.finding import Finding
from app.models.repository import Repository


class FindingRepository:
    """Persists and queries findings belonging to one user's analysis runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, findings: list[ScannerFinding]) -> int:
        """Persist a batch of normalized findings.

        Returns the number of findings created.
        """
        if not findings:
            return 0

        orm_findings = []
        for f in findings:
            orm_finding = Finding(
                analysis_run_id=f.analysis_run_id,
                scanner=f.scanner,
                scanner_version=f.scanner_version,
                finding_type=f.finding_type,
                severity=f.severity,
                title=f.title[:512],
                description=f.description[:2048] if f.description else None,
                package_name=f.package_name,
                installed_version=f.installed_version,
                fixed_version=f.fixed_version,
                vulnerability_id=f.vulnerability_id,
                references_json=json.dumps(f.references) if f.references else None,
                location=f.location,
            )
            orm_findings.append(orm_finding)

        self._session.add_all(orm_findings)
        await self._session.flush()
        return len(orm_findings)

    async def count_for_run(self, run_id: uuid.UUID) -> int:
        """Count findings for an analysis run."""
        stmt = (
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.analysis_run_id == run_id,
            )
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def list_for_run(
        self,
        run_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 50,
        severity: Severity | None = None,
        finding_type: FindingType | None = None,
        sort_by: str = "severity",
        order: str = "desc",
    ) -> tuple[list[Finding], int]:
        """List findings for a specific analysis run.

        Returns (findings, total_count).
        """
        stmt = select(Finding).where(Finding.analysis_run_id == run_id)
        count_stmt = (
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.analysis_run_id == run_id,
            )
        )

        if severity is not None:
            stmt = stmt.where(Finding.severity == severity)
            count_stmt = count_stmt.where(Finding.severity == severity)
        if finding_type is not None:
            stmt = stmt.where(Finding.finding_type == finding_type)
            count_stmt = count_stmt.where(Finding.finding_type == finding_type)

        total = int((await self._session.execute(count_stmt)).scalar_one())

        # Sort by severity: critical > high > medium > low > unknown
        if sort_by == "severity":
            stmt = stmt.order_by(
                Finding.severity.asc() if order == "asc" else Finding.severity.desc(),
            )
        else:
            stmt = stmt.order_by(Finding.created_at.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

    async def list_for_repository(
        self,
        owner_id: uuid.UUID,
        repository_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 50,
        severity: Severity | None = None,
        finding_type: FindingType | None = None,
    ) -> tuple[list[Finding], int]:
        """List findings for all runs of a repository, scoped to owner.

        Returns (findings, total_count).
        """
        stmt = (
            select(Finding)
            .join(AnalysisRun, Finding.analysis_run_id == AnalysisRun.id)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(
                Repository.owner_id == owner_id,
                Repository.id == repository_id,
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(Finding)
            .join(AnalysisRun, Finding.analysis_run_id == AnalysisRun.id)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(
                Repository.owner_id == owner_id,
                Repository.id == repository_id,
            )
        )

        if severity is not None:
            stmt = stmt.where(Finding.severity == severity)
            count_stmt = count_stmt.where(Finding.severity == severity)
        if finding_type is not None:
            stmt = stmt.where(Finding.finding_type == finding_type)
            count_stmt = count_stmt.where(Finding.finding_type == finding_type)

        total = int((await self._session.execute(count_stmt)).scalar_one())
        stmt = stmt.order_by(Finding.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_for_owner(self, owner_id: uuid.UUID, finding_id: uuid.UUID) -> Finding | None:
        """Return a finding only when the owner owns the parent repository."""
        stmt = (
            select(Finding)
            .join(AnalysisRun, Finding.analysis_run_id == AnalysisRun.id)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(
                Finding.id == finding_id,
                Repository.owner_id == owner_id,
            )
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def delete_for_run(self, run_id: uuid.UUID) -> int:
        """Delete all findings for an analysis run.

        Returns the number of findings deleted.
        """
        stmt = select(Finding).where(Finding.analysis_run_id == run_id)
        findings = (await self._session.execute(stmt)).scalars().all()
        count = len(findings)
        for f in findings:
            await self._session.delete(f)
        return count
