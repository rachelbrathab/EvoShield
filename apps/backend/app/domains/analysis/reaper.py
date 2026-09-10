"""Stranded-run recovery (Sprint 8).

Analysis execution lives in in-process ``asyncio`` tasks (a deliberate
Sprint 4A decision — see ADR 0008): the run state machine, ports and API do
not depend on the execution mechanism. The trade-off is that a server
restart orphans the runs whose tasks died with the process. Without
recovery, a restarted server would report ``queued``/``running`` analyses
forever, the repository would stay ``analyzing``, and the DB-level
single-active-run guard would block every future start for that repository.

The reaper closes that hole at startup: every active run is transitioned to
FAILED with an explanatory ``failure_reason``, its PENDING/RUNNING scanner
runs are marked FAILED, and each repository's lifecycle status is reset to
``failed``. Terminal runs are never touched, and a reaper-vs-background-task
race cannot corrupt state because every write goes through the orchestrator's
transition guard (``_ALLOWED_FROM``), which refuses terminal or unexpected
sources.

Recovery is deliberately *not* automatic re-queueing: scans require fresh
acquisition (a clone that no longer exists) and operator intent, so runs are
marked failed and simply re-startable from the UI/API.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.analysis.orchestrator import _elapsed_ms
from app.domains.scanners.scanner_run_repository import ScannerRunRepository
from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.repository import AnalysisStatus, Repository
from app.models.scanner_run import ScannerRunStatus

logger = logging.getLogger(__name__)

_RECOVERED_REASON = (
    "Analysis run interrupted by a server restart and marked failed; start a new run to re-scan."
)


async def recover_stranded_runs(session: AsyncSession) -> list[uuid.UUID]:
    """Mark every active analysis run as failed and reset its repository.

    Intended for application startup, when no in-process run task can exist.
    With multiple workers behind one load balancer, run this from a one-off
    migration/entrypoint command instead of ``create_app`` (compose's migrate
    service does exactly that).

    Returns the ids of the recovered runs (logged, never exposed to users).
    """
    stmt = select(AnalysisRun).where(
        AnalysisRun.status.in_((AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING))
    )
    stranded = list((await session.execute(stmt)).scalars().all())

    recovered: list[uuid.UUID] = []
    if not stranded:
        return recovered

    repository_ids: set[uuid.UUID] = set()
    for run in stranded:
        repository_ids.add(run.repository_id)
        # A run is only ever QUEUED or RUNNING here, and no background task
        # exists at startup — the transition is legal by construction.
        run.status = AnalysisRunStatus.FAILED
        now = datetime.now(UTC)
        run.completed_at = now
        if run.started_at is not None:
            run.duration_ms = _elapsed_ms(run.started_at, now)
        run.failure_reason = _RECOVERED_REASON
        recovered.append(run.id)

        # Scanner runs are transitioned through their repository helper, which
        # only touches PENDING/RUNNING rows (SKIPPED/CANCELLED stay as-is).
        sr_repo = ScannerRunRepository(session)
        for sr in await sr_repo.list_for_analysis(run.id):
            if sr.status in (ScannerRunStatus.PENDING, ScannerRunStatus.RUNNING):
                await sr_repo.mark_failed(sr.id, reason=_RECOVERED_REASON)

    # Reset each affected repository's lifecycle status.
    for repository_id in repository_ids:
        repository = await session.get(Repository, repository_id)
        if repository is not None and repository.analysis_status in (
            AnalysisStatus.QUEUED,
            AnalysisStatus.ANALYZING,
        ):
            repository.analysis_status = AnalysisStatus.FAILED

    await session.commit()

    logger.warning(
        "Reaper recovered %d stranded analysis run(s): %s",
        len(recovered),
        ", ".join(str(r) for r in recovered),
    )
    return recovered
