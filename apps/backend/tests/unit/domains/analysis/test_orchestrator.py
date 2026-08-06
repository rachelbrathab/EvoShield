"""AnalysisOrchestrator unit tests (Sprint 4A).

Exercise the run state machine against the real test database with a
controllable provider stub: queue → running → completed, provider failures,
timeouts, cancellation (queued and running), duplicate-active rejection and
owner scoping. The background execution task uses the shared test
`session_factory`, so runs are observed by polling fresh sessions.
"""

import asyncio
import time
import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ProviderError
from app.db.session import session_factory
from app.domains.analysis.orchestrator import AnalysisOrchestrator
from app.domains.analysis.providers.fake import FakeAnalysisProvider
from app.domains.analysis.repository import AnalysisRunRepository
from app.models.analysis_run import AnalysisRunStatus
from app.models.repository import AnalysisStatus, Repository
from app.models.user import User


class StubProvider:
    """Controllable AnalysisProvider: fixed delay, optional injected failure."""

    name = "stub"
    version = "9.9.9"

    def __init__(self, delay: float = 0.0, fail_with: Exception | None = None) -> None:
        self.delay = delay
        self.fail_with = fail_with
        self.executed = False

    def supports(self, repository) -> bool:
        return True

    async def execute(self, context) -> None:
        self.executed = True
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_with is not None:
            raise self.fail_with


async def _make_user() -> uuid.UUID:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email=f"analysis-{uuid.uuid4().hex[:8]}@example.com",
                auth_provider="local",
            )
        )
        await session.commit()
    return user_id


async def _make_repo(user_id: uuid.UUID, full_name: str = "octocat/alpha") -> Repository:
    async with session_factory() as session:
        repo = Repository(
            owner_id=user_id,
            provider="github",
            name=full_name.split("/")[-1],
            full_name=full_name,
            analysis_status=AnalysisStatus.NOT_ANALYZED,
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        return repo


async def _wait_for_status(
    run_id: uuid.UUID,
    expected: AnalysisRunStatus,
    max_wait: float = 8.0,
) -> None:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        async with session_factory() as session:
            run = await AnalysisRunRepository(session).get(run_id)
        if run is not None and run.status == expected:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} never reached {expected.value}")


async def _repo_status(repository_id: uuid.UUID) -> AnalysisStatus:
    async with session_factory() as session:
        repo = await session.get(Repository, repository_id)
        assert repo is not None
        return repo.analysis_status


def test_start_queues_run_and_background_task_completes_it() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner)
        provider = StubProvider()
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=provider,
                queued_hold_seconds=0.0,
                timeout_seconds=30.0,
            )
            run, full_name = await orchestrator.start(repo.id, owner)

        assert run.status is AnalysisRunStatus.QUEUED
        assert full_name == "octocat/alpha"
        assert run.analysis_version == "9.9.9"

        await _wait_for_status(run.id, AnalysisRunStatus.COMPLETED)

        async with session_factory() as session:
            done = await AnalysisRunRepository(session).get(run.id)
            assert done is not None
            assert done.started_at is not None
            assert done.completed_at is not None
            assert done.duration_ms is not None and done.duration_ms >= 0

        assert await _repo_status(repo.id) is AnalysisStatus.ANALYZED
        async with session_factory() as session:
            updated_repo = await session.get(Repository, repo.id)
            assert updated_repo is not None
            assert updated_repo.last_analysis_job_id == str(run.id)
            assert updated_repo.last_analysis_at is not None

    asyncio.run(scenario())


def test_start_rejects_when_run_already_active() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=StubProvider(),
                queued_hold_seconds=60.0,  # keep the first run QUEUED
                timeout_seconds=30.0,
            )
            run, _ = await orchestrator.start(repo.id, owner)
            with pytest.raises(ConflictError) as excinfo:
                await orchestrator.start(repo.id, owner)
            assert excinfo.value.code == "analysis_already_active"
            # Clean up so the sleeping task aborts.
            await orchestrator.cancel(owner, run.id)

    asyncio.run(scenario())


def test_start_requires_owned_repository() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        other = await _make_user()
        repo = await _make_repo(owner)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=StubProvider(),
                queued_hold_seconds=0.0,
                timeout_seconds=30.0,
            )
            with pytest.raises(NotFoundError):
                await orchestrator.start(repo.id, other)

    asyncio.run(scenario())


def test_cancel_queued_run_aborts_the_task() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=FakeAnalysisProvider(delay_seconds=5.0),
                queued_hold_seconds=60.0,
                timeout_seconds=120.0,
            )
            run, _ = await orchestrator.start(repo.id, owner)
            cancelled, _ = await orchestrator.cancel(owner, run.id)

        assert cancelled.status is AnalysisRunStatus.CANCELLED
        assert await _repo_status(repo.id) is AnalysisStatus.NOT_ANALYZED
        # Give the background task a moment — it must not overwrite CANCELLED.
        await asyncio.sleep(0.1)
        async with session_factory() as session:
            stored = await AnalysisRunRepository(session).get(run.id)
            assert stored is not None
            assert stored.status is AnalysisRunStatus.CANCELLED

    asyncio.run(scenario())


def test_cancel_running_run_stays_cancelled() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=FakeAnalysisProvider(delay_seconds=5.0),
                queued_hold_seconds=0.0,
                timeout_seconds=120.0,
            )
            run, _ = await orchestrator.start(repo.id, owner)

        await _wait_for_status(run.id, AnalysisRunStatus.RUNNING)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=FakeAnalysisProvider(delay_seconds=5.0),
                queued_hold_seconds=0.0,
                timeout_seconds=120.0,
            )
            cancelled, _ = await orchestrator.cancel(owner, run.id)

        assert cancelled.status is AnalysisRunStatus.CANCELLED
        # The provider observes the cancel event and aborts; the run stays
        # CANCELLED (the transition guard blocks any late COMPLETED write).
        await _wait_for_status(run.id, AnalysisRunStatus.CANCELLED)
        await asyncio.sleep(0.1)
        async with session_factory() as session:
            stored = await AnalysisRunRepository(session).get(run.id)
            assert stored is not None
            assert stored.status is AnalysisRunStatus.CANCELLED

    asyncio.run(scenario())


def test_cancel_terminal_run_conflicts() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=StubProvider(),
                queued_hold_seconds=0.0,
                timeout_seconds=30.0,
            )
            run, _ = await orchestrator.start(repo.id, owner)
            await _wait_for_status(run.id, AnalysisRunStatus.COMPLETED)
            with pytest.raises(ConflictError) as excinfo:
                await orchestrator.cancel(owner, run.id)
            assert excinfo.value.code == "analysis_not_cancellable"

    asyncio.run(scenario())


def test_provider_failure_marks_run_failed() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=StubProvider(fail_with=ProviderError("scanner exploded")),
                queued_hold_seconds=0.0,
                timeout_seconds=30.0,
            )
            run, _ = await orchestrator.start(repo.id, owner)

        await _wait_for_status(run.id, AnalysisRunStatus.FAILED)
        async with session_factory() as session:
            stored = await AnalysisRunRepository(session).get(run.id)
            assert stored is not None
            assert stored.failure_reason is not None
            assert "scanner exploded" in stored.failure_reason
        assert await _repo_status(repo.id) is AnalysisStatus.FAILED

    asyncio.run(scenario())


def test_timeout_marks_run_failed() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo = await _make_repo(owner)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=StubProvider(delay=5.0),
                queued_hold_seconds=0.0,
                timeout_seconds=0.1,
            )
            run, _ = await orchestrator.start(repo.id, owner)

        await _wait_for_status(run.id, AnalysisRunStatus.FAILED)
        async with session_factory() as session:
            stored = await AnalysisRunRepository(session).get(run.id)
            assert stored is not None
            assert stored.failure_reason is not None
            assert "timed out" in stored.failure_reason

    asyncio.run(scenario())


def test_get_list_delete_are_owner_scoped() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        other = await _make_user()
        repo = await _make_repo(owner)
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=StubProvider(),
                queued_hold_seconds=0.0,
                timeout_seconds=30.0,
            )
            run, _ = await orchestrator.start(repo.id, owner)
            await _wait_for_status(run.id, AnalysisRunStatus.COMPLETED)

            # Other user cannot see, cancel, or delete it.
            with pytest.raises(NotFoundError):
                await orchestrator.get(other, run.id)
            with pytest.raises(NotFoundError):
                await orchestrator.cancel(other, run.id)
            with pytest.raises(NotFoundError):
                await orchestrator.delete(other, run.id)

            # Owner can list (with the repository name) and delete it.
            rows, total = await orchestrator.list(owner, page=1, page_size=20)
            assert total == 1
            assert rows[0][0].id == run.id
            assert rows[0][1] == "octocat/alpha"

            # Deleting an active run conflicts.
            async with session_factory() as session:
                blocking = AnalysisOrchestrator(
                    session=session,
                    session_factory=session_factory,
                    provider=StubProvider(),
                    queued_hold_seconds=60.0,
                    timeout_seconds=30.0,
                )
                active, _ = await blocking.start(repo.id, owner)
                with pytest.raises(ConflictError) as excinfo:
                    await blocking.delete(owner, active.id)
                assert excinfo.value.code == "analysis_active"
                await blocking.cancel(owner, active.id)

            await orchestrator.delete(owner, run.id)
            with pytest.raises(NotFoundError):
                await orchestrator.get(owner, run.id)

    asyncio.run(scenario())


def test_list_filters_by_repository_and_status() -> None:
    async def scenario() -> None:
        owner = await _make_user()
        repo_a = await _make_repo(owner, "octocat/alpha")
        repo_b = await _make_repo(owner, "octocat/beta")
        async with session_factory() as session:
            orchestrator = AnalysisOrchestrator(
                session=session,
                session_factory=session_factory,
                provider=StubProvider(),
                queued_hold_seconds=0.0,
                timeout_seconds=30.0,
            )
            run_a, _ = await orchestrator.start(repo_a.id, owner)
            run_b, _ = await orchestrator.start(repo_b.id, owner)
            await _wait_for_status(run_a.id, AnalysisRunStatus.COMPLETED)
            await _wait_for_status(run_b.id, AnalysisRunStatus.COMPLETED)

            per_repo, total = await orchestrator.list(
                owner, page=1, page_size=20, repository_id=repo_a.id
            )
            assert total == 1
            assert per_repo[0][0].id == run_a.id

            completed, total_completed = await orchestrator.list(
                owner, page=1, page_size=20, status=AnalysisRunStatus.COMPLETED
            )
            assert total_completed == 2
            assert {row[0].id for row in completed} == {run_a.id, run_b.id}

            paged, total_paged = await orchestrator.list(owner, page=1, page_size=1)
            assert len(paged) == 1
            assert total_paged == 2

    asyncio.run(scenario())
