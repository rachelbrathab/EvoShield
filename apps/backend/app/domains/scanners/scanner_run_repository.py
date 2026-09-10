"""ScannerRun data access — CRUD and lifecycle helpers for the ``scanner_runs`` table.

Each method is a thin data-access wrapper; business rules (status
validation, aggregation) live in the orchestrator.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scanner_run import ScannerRun, ScannerRunStatus


def _elapsed_ms(started_at: datetime, ended_at: datetime) -> int:
    """Milliseconds between two timestamps, tolerating naive DB values.

    SQLite returns naive datetimes even for ``DateTime(timezone=True)``
    columns; Postgres returns aware ones. Mirrors the orchestrator's
    tolerant helper so lifecycle math never crashes on a dialect switch.
    """

    def _utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    return max(0, int((_utc(ended_at) - _utc(started_at)).total_seconds() * 1000))


class ScannerRunRepository:
    """Persists and queries ScannerRun rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Create ──────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        analysis_run_id: uuid.UUID,
        scanner_name: str,
        scanner_version: str,
    ) -> ScannerRun:
        """Create a PENDING ScannerRun."""
        run = ScannerRun(
            analysis_run_id=analysis_run_id,
            scanner_name=scanner_name,
            scanner_version=scanner_version,
            status=ScannerRunStatus.PENDING,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    # ── Read ────────────────────────────────────────────────────────────

    async def get(self, scanner_run_id: uuid.UUID) -> ScannerRun | None:
        stmt = select(ScannerRun).where(ScannerRun.id == scanner_run_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_analysis(
        self,
        analysis_run_id: uuid.UUID,
    ) -> list[ScannerRun]:
        """Return all ScannerRuns for an AnalysisRun, ordered by creation."""
        stmt = (
            select(ScannerRun)
            .where(ScannerRun.analysis_run_id == analysis_run_id)
            .order_by(ScannerRun.created_at.asc(), ScannerRun.id.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_findings(self, scanner_run_id: uuid.UUID) -> int:
        """Count findings attributed to this ScannerRun.

        Note: findings are linked to ``analysis_run_id`` today; this counts
        findings whose ``scanner`` matches the ScannerRun's ``scanner_name``.
        """
        from app.models.finding import Finding

        scanner = await self.get(scanner_run_id)
        if scanner is None:
            return 0
        stmt = (
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.analysis_run_id == scanner.analysis_run_id,
                Finding.scanner == scanner.scanner_name,
            )
        )
        return int((await self._session.execute(stmt)).scalar_one())

    # ── Lifecycle transitions ───────────────────────────────────────────

    async def mark_running(self, scanner_run_id: uuid.UUID) -> ScannerRun | None:
        run = await self.get(scanner_run_id)
        if run is None or run.status != ScannerRunStatus.PENDING:
            return run
        run.status = ScannerRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        await self._session.flush()
        return run

    async def mark_completed(
        self,
        scanner_run_id: uuid.UUID,
        *,
        finding_count: int | None = None,
        component_count: int | None = None,
    ) -> ScannerRun | None:
        run = await self.get(scanner_run_id)
        if run is None or run.status != ScannerRunStatus.RUNNING:
            return run
        now = datetime.now(UTC)
        run.status = ScannerRunStatus.COMPLETED
        run.completed_at = now
        if run.started_at is not None:
            run.duration_ms = _elapsed_ms(run.started_at, now)
        if finding_count is not None:
            run.finding_count = finding_count
        if component_count is not None:
            run.component_count = component_count
        await self._session.flush()
        return run

    async def mark_failed(
        self,
        scanner_run_id: uuid.UUID,
        *,
        reason: str,
    ) -> ScannerRun | None:
        run = await self.get(scanner_run_id)
        if run is None or run.status not in (
            ScannerRunStatus.PENDING,
            ScannerRunStatus.RUNNING,
        ):
            return run
        now = datetime.now(UTC)
        run.status = ScannerRunStatus.FAILED
        run.completed_at = now
        if run.started_at is not None:
            run.duration_ms = _elapsed_ms(run.started_at, now)
        run.failure_reason = reason[:512]
        await self._session.flush()
        return run

    async def mark_cancelled(self, scanner_run_id: uuid.UUID) -> ScannerRun | None:
        run = await self.get(scanner_run_id)
        if run is None or run.status not in (
            ScannerRunStatus.PENDING,
            ScannerRunStatus.RUNNING,
        ):
            return run
        now = datetime.now(UTC)
        run.status = ScannerRunStatus.CANCELLED
        run.completed_at = now
        if run.started_at is not None:
            run.duration_ms = _elapsed_ms(run.started_at, now)
        await self._session.flush()
        return run

    async def mark_skipped(
        self,
        scanner_run_id: uuid.UUID,
        *,
        reason: str = "skipped",
    ) -> ScannerRun | None:
        run = await self.get(scanner_run_id)
        if run is None or run.status != ScannerRunStatus.PENDING:
            return run
        run.status = ScannerRunStatus.SKIPPED
        run.failure_reason = reason[:512]
        await self._session.flush()
        return run
