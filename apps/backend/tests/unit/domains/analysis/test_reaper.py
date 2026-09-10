"""Stranded-run recovery tests (Sprint 8).

The reaper must (1) fail every queued/running run with an explanatory
reason, (2) fail only PENDING/RUNNING scanner runs, (3) reset a repository
stuck in queued/analyzing, (4) leave terminal runs and analyzed/failed
repositories untouched, and (5) un-block new runs by releasing the
DB-level single-active-run guard.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from app.db.session import session_factory
from app.domains.analysis.reaper import recover_stranded_runs
from app.domains.analysis.repository import AnalysisRunRepository
from app.domains.scanners.scanner_run_repository import ScannerRunRepository
from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.repository import AnalysisStatus, Repository
from app.models.scanner_run import ScannerRun, ScannerRunStatus
from app.models.user import User


async def _make_user() -> uuid.UUID:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email=f"reaper-{uuid.uuid4().hex[:8]}@example.com",
                auth_provider="local",
            )
        )
        await session.commit()
    return user_id


async def _make_repo(
    owner_id: uuid.UUID,
    *,
    analysis_status: AnalysisStatus = AnalysisStatus.NOT_ANALYZED,
    full_name: str | None = None,
) -> Repository:
    full_name = full_name or f"octocat/alpha-{uuid.uuid4().hex[:8]}"
    async with session_factory() as session:
        repo = Repository(
            owner_id=owner_id,
            provider="github",
            name=full_name.split("/")[-1],
            full_name=full_name,
            analysis_status=analysis_status,
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        return repo


async def _make_run(repository_id: uuid.UUID, status: AnalysisRunStatus) -> AnalysisRun:
    async with session_factory() as session:
        run = AnalysisRun(
            repository_id=repository_id,
            triggered_by="user",
            status=status,
            analysis_version="test",
        )
        if status is AnalysisRunStatus.RUNNING:
            run.started_at = datetime.now(UTC)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


async def _make_scanner_run(analysis_run_id: uuid.UUID, status: ScannerRunStatus) -> uuid.UUID:
    async with session_factory() as session:
        sr = ScannerRun(
            analysis_run_id=analysis_run_id,
            scanner_name="trivy",
            scanner_version="0.74.0",
            status=ScannerRunStatus.PENDING,
        )
        session.add(sr)
        await session.commit()
        sr_id = sr.id

    if status is ScannerRunStatus.PENDING:
        return sr_id
    async with session_factory() as session:
        sr_repo = ScannerRunRepository(session)
        if status is ScannerRunStatus.RUNNING:
            await sr_repo.mark_running(sr_id)
        else:
            await sr_repo.mark_running(sr_id)
            await sr_repo.mark_completed(sr_id)
        await session.commit()
    return sr_id


def test_reaper_fails_stranded_runs_and_resets_repository() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner, analysis_status=AnalysisStatus.ANALYZING)
        run = await _make_run(repo.id, AnalysisRunStatus.RUNNING)
        running_sr = await _make_scanner_run(run.id, ScannerRunStatus.RUNNING)
        completed_sr = await _make_scanner_run(run.id, ScannerRunStatus.COMPLETED)

        async with session_factory() as session:
            recovered = await recover_stranded_runs(session)

        assert recovered == [run.id]
        async with session_factory() as session:
            stored = await AnalysisRunRepository(session).get(run.id)
            assert stored is not None
            assert stored.status is AnalysisRunStatus.FAILED
            assert stored.failure_reason is not None
            assert "restart" in stored.failure_reason
            assert stored.completed_at is not None
            assert stored.duration_ms is not None

            async with session_factory() as session:
                sr_repo = ScannerRunRepository(session)
                failed_sr = await sr_repo.get(running_sr)
                assert failed_sr is not None
                assert failed_sr.status is ScannerRunStatus.FAILED
                assert failed_sr.failure_reason is not None
                untouched_sr = await sr_repo.get(completed_sr)
                assert untouched_sr is not None
                assert untouched_sr.status is ScannerRunStatus.COMPLETED

        async with session_factory() as session:
            updated_repo = await session.get(Repository, repo.id)
            assert updated_repo is not None
            assert updated_repo.analysis_status is AnalysisStatus.FAILED

    asyncio.run(scenario())


def test_reaper_fails_queued_run_and_reset_queued_repository() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner, analysis_status=AnalysisStatus.QUEUED)
        run = await _make_run(repo.id, AnalysisRunStatus.QUEUED)

        async with session_factory() as session:
            recovered = await recover_stranded_runs(session)

        assert recovered == [run.id]
        async with session_factory() as session:
            stored = await AnalysisRunRepository(session).get(run.id)
            assert stored is not None
            assert stored.status is AnalysisRunStatus.FAILED
            # A QUEUED run never started — no duration is computed.
            assert stored.duration_ms is None
            updated_repo = await session.get(Repository, repo.id)
            assert updated_repo is not None
            assert updated_repo.analysis_status is AnalysisStatus.FAILED

    asyncio.run(scenario())


def test_reaper_leaves_terminal_runs_and_repositories_alone() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        analyzed_repo = await _make_repo(
            owner, analysis_status=AnalysisStatus.ANALYZED, full_name="octocat/gamma"
        )
        failed_repo = await _make_repo(
            owner, analysis_status=AnalysisStatus.FAILED, full_name="octocat/delta"
        )
        completed = await _make_run(analyzed_repo.id, AnalysisRunStatus.COMPLETED)
        cancelled = await _make_run(failed_repo.id, AnalysisRunStatus.CANCELLED)

        async with session_factory() as session:
            recovered = await recover_stranded_runs(session)

        assert recovered == []
        async with session_factory() as session:
            still_completed = await AnalysisRunRepository(session).get(completed.id)
            assert still_completed is not None
            assert still_completed.status is AnalysisRunStatus.COMPLETED
            still_cancelled = await AnalysisRunRepository(session).get(cancelled.id)
            assert still_cancelled is not None
            assert still_cancelled.status is AnalysisRunStatus.CANCELLED
            repo = await session.get(Repository, analyzed_repo.id)
            assert repo is not None
            assert repo.analysis_status is AnalysisStatus.ANALYZED

    asyncio.run(scenario())


def test_reaper_unblocks_new_runs_after_restart() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner, analysis_status=AnalysisStatus.ANALYZING)
        stranded = await _make_run(repo.id, AnalysisRunStatus.RUNNING)

        async with session_factory() as session:
            await recover_stranded_runs(session)

        # The DB-level single-active-run guard is released: starting a fresh
        # run must succeed and complete (this is the user-visible outcome).
        from tests.unit.domains.analysis.test_orchestrator import StubProvider

        async with session_factory() as session:
            from app.domains.analysis.orchestrator import AnalysisOrchestrator

            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=StubProvider(),
                queued_hold_seconds=0.0,
                timeout_seconds=30.0,
            )
            new_run, _ = await orchestrator.start(repo.id, owner)

        assert new_run.status is AnalysisRunStatus.QUEUED
        deadline = datetime.now(UTC).timestamp() + 8
        while datetime.now(UTC).timestamp() < deadline:
            async with session_factory() as session:
                stored = await AnalysisRunRepository(session).get(new_run.id)
            if stored is not None and stored.status is AnalysisRunStatus.COMPLETED:
                break
            await asyncio.sleep(0.02)
        else:
            raise AssertionError("new run never completed after recovery")

        async with session_factory() as session:
            old = await AnalysisRunRepository(session).get(stranded.id)
            assert old is not None
            assert old.status is AnalysisRunStatus.FAILED

    asyncio.run(scenario())
