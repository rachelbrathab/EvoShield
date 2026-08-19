"""AnalysisOrchestrator — the state machine that runs the analysis pipeline.

Sprint 4A builds the *operating system* for the analysis engine; the
orchestrator owns the lifecycle and knows nothing about any scanner:

- **Create** a run (QUEUED), rejecting when the repository already has an
  active run.
- **Dispatch** it after a configurable queue hold, mirroring the repository
  lifecycle status (queued → analyzing → analyzed / failed / not_analyzed).
- **Execute** the injected `AnalysisProvider` under a hard timeout, recording
  timing and outcome; failures land in `failure_reason`.
- **Cancel** a queued or running run via a per-run `asyncio.Event` the
  provider polls; cancel while running never clobbers the terminal state.

Execution is an in-process asyncio task (the dev simulation path). Real
background workers replace the task in Sprint 5 — the state machine, ports and
API do not change.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.analysis.ports import (
    AnalysisCancelledError,
    AnalysisExecutionContext,
    AnalysisProvider,
)
from app.domains.analysis.repository import AnalysisRunRepository
from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.repository import AnalysisStatus, Repository

logger = logging.getLogger(__name__)

#: Legal transitions: target state -> set of states it may come from.
_ALLOWED_FROM: dict[AnalysisRunStatus, frozenset[AnalysisRunStatus]] = {
    AnalysisRunStatus.RUNNING: frozenset({AnalysisRunStatus.QUEUED}),
    AnalysisRunStatus.COMPLETED: frozenset({AnalysisRunStatus.RUNNING}),
    AnalysisRunStatus.FAILED: frozenset({AnalysisRunStatus.RUNNING}),
    AnalysisRunStatus.CANCELLED: frozenset({AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING}),
}

#: Repository-level lifecycle state mirrored for each run state.
_REPOSITORY_STATUS: dict[AnalysisRunStatus, AnalysisStatus] = {
    AnalysisRunStatus.QUEUED: AnalysisStatus.QUEUED,
    AnalysisRunStatus.RUNNING: AnalysisStatus.ANALYZING,
    AnalysisRunStatus.COMPLETED: AnalysisStatus.ANALYZED,
    AnalysisRunStatus.FAILED: AnalysisStatus.FAILED,
    AnalysisRunStatus.CANCELLED: AnalysisStatus.NOT_ANALYZED,
}

_TERMINAL = frozenset(
    {
        AnalysisRunStatus.COMPLETED,
        AnalysisRunStatus.FAILED,
        AnalysisRunStatus.CANCELLED,
    }
)

_ACTIVE = frozenset({AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING})


class AnalysisOrchestrator:
    """Coordinates analysis run lifecycles against a provider."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        provider: AnalysisProvider,
        queued_hold_seconds: float = 2.0,
        timeout_seconds: float = 120.0,
        token_resolver_factory: (
            Callable[[uuid.UUID], Callable[[], Awaitable[str | None]]] | None
        ) = None,
    ) -> None:
        self._session = session
        # Request-scoped runs repository (bound to the injected session).
        self._runs = AnalysisRunRepository(session)
        # Session factory for the background task, which outlives the request.
        self._session_factory = session_factory
        self._provider = provider
        self._queued_hold_seconds = max(0.0, queued_hold_seconds)
        self._timeout_seconds = max(0.1, timeout_seconds)
        self._token_resolver_factory = token_resolver_factory
        # Per-run cancellation events (also lets the background task abort).
        self._cancel_events: dict[uuid.UUID, asyncio.Event] = {}
        # Strong references so in-flight tasks are not garbage-collected.
        self._tasks: set[asyncio.Task[None]] = set()
        # Owner mapping for background tasks (run_id → owner_id).
        self._run_owners: dict[uuid.UUID, uuid.UUID] = {}

    # ── Public API ──────────────────────────────────────────────────────
    async def start(
        self,
        repository_id: uuid.UUID,
        owner_id: uuid.UUID,
        *,
        triggered_by: str = "user",
    ) -> tuple[AnalysisRun, str]:
        """Create a QUEUED run and dispatch it in the background.

        Returns (run, repository_full_name). Rejects when the repository is
        not owned (404) or already has an active run (409).
        """
        repository = await self._runs.get_repository_for_owner(owner_id, repository_id)
        if repository is None:
            raise NotFoundError("Repository not found.")

        active = await self._runs.get_active_for_repository(repository_id)
        if active is not None:
            raise ConflictError(
                f"This repository already has an analysis in progress ({active.status.value}).",
                code="analysis_already_active",
            )

        run = AnalysisRun(
            repository_id=repository_id,
            triggered_by=triggered_by,
            status=AnalysisRunStatus.QUEUED,
            analysis_version=self._provider.version,
        )
        self._session.add(run)
        repository.analysis_status = _REPOSITORY_STATUS[AnalysisRunStatus.QUEUED]
        try:
            await self._session.commit()
        except IntegrityError:
            # A concurrent start won the race: the filtered unique index on
            # active runs rejects the second QUEUED row at the database. Turn
            # that into the documented 409 rather than a 500.
            await self._session.rollback()
            raise ConflictError(
                "This repository already has an analysis in progress.",
                code="analysis_already_active",
            ) from None
        await self._session.refresh(run)

        self._schedule(run.id, owner_id)
        logger.info(
            "Analysis run %s queued for repository %s (provider=%s)",
            run.id,
            repository.full_name,
            self._provider.name,
        )
        return run, repository.full_name

    async def get(self, owner_id: uuid.UUID, run_id: uuid.UUID) -> tuple[AnalysisRun, str | None]:
        row = await self._runs.get_for_owner(owner_id, run_id)
        if row is None:
            raise NotFoundError("Analysis run not found.")
        return row

    async def list(
        self,
        owner_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        repository_id: uuid.UUID | None = None,
        status: AnalysisRunStatus | None = None,
    ) -> tuple[list[tuple[AnalysisRun, str]], int]:
        rows, total = await self._runs.list_for_owner(
            owner_id,
            page=page,
            page_size=page_size,
            repository_id=repository_id,
            status=status,
        )
        return list(rows), total

    async def cancel(
        self, owner_id: uuid.UUID, run_id: uuid.UUID
    ) -> tuple[AnalysisRun, str | None]:
        """Cancel a queued or running run. Terminal runs are a 409 conflict.

        Returns (run, repository_full_name) so the API can label the run.
        """
        row = await self._runs.get_for_owner(owner_id, run_id)
        if row is None:
            raise NotFoundError("Analysis run not found.")
        run, full_name = row
        # The identity map may hold a stale status (the background task may
        # have completed the run since it was first loaded in this session).
        await self._session.refresh(run)
        if run.status not in _ACTIVE:
            raise ConflictError(
                f"Cannot cancel a {run.status.value} analysis.",
                code="analysis_not_cancellable",
            )

        event = self._cancel_events.get(run_id)
        if event is not None:
            event.set()

        now = datetime.now(UTC)
        run.status = AnalysisRunStatus.CANCELLED
        run.completed_at = now
        if run.started_at is not None:
            run.duration_ms = _elapsed_ms(run.started_at, now)
        await self._sync_repository_status(self._session, run, AnalysisRunStatus.CANCELLED)
        await self._session.commit()
        await self._session.refresh(run)
        logger.info("Analysis run %s cancelled", run_id)
        return run, full_name

    async def delete(self, owner_id: uuid.UUID, run_id: uuid.UUID) -> None:
        """Delete a terminal run. Active runs are a 409 conflict."""
        row = await self._runs.get_for_owner(owner_id, run_id)
        if row is None:
            raise NotFoundError("Analysis run not found.")
        run, _ = row
        # Fresh status — the identity map may predate a background transition.
        await self._session.refresh(run)
        if run.status in _ACTIVE:
            raise ConflictError(
                "Cannot delete an active analysis run.",
                code="analysis_active",
            )
        await self._session.delete(run)
        await self._session.commit()

    # ── Background execution ────────────────────────────────────────────
    def _schedule(self, run_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        self._run_owners[run_id] = owner_id
        task = asyncio.create_task(self._execute_run(run_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _execute_run(self, run_id: uuid.UUID) -> None:
        try:
            # 1) Queue hold — a cancellation during this phase aborts cleanly.
            await asyncio.sleep(self._queued_hold_seconds)
            row = await self._load_with_name(run_id)
            if row is None or row[0].status != AnalysisRunStatus.QUEUED:
                return  # cancelled (or deleted) while still queued
            run, full_name = row
            cancel_event = self._cancel_events.get(run_id)
            if cancel_event is None:
                cancel_event = asyncio.Event()
                self._cancel_events[run_id] = cancel_event

            # 2) Running — mirrors the repository lifecycle to ANALYZING.
            try:
                await self._transition(run_id, AnalysisRunStatus.RUNNING)
            except ConflictError:
                return  # cancelled between the reload and the transition

            owner_id = self._run_owners.pop(run_id, uuid.UUID(int=0))
            token_resolver: Callable[[], Awaitable[str | None]]
            if self._token_resolver_factory is not None:
                token_resolver = self._token_resolver_factory(owner_id)
            else:
                from app.domains.analysis.ports import _make_noop_resolver

                token_resolver = _make_noop_resolver()

            context = AnalysisExecutionContext(
                run_id=run_id,
                repository_id=run.repository_id,
                full_name=full_name or "",
                cancel_event=cancel_event,
                owner_id=owner_id,
                token_resolver=token_resolver,
            )
            try:
                await asyncio.wait_for(
                    self._provider.execute(context),
                    timeout=self._timeout_seconds,
                )
            except AnalysisCancelledError:
                return  # the cancel handler already set CANCELLED
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                await self._fail(
                    run_id,
                    f"Provider timed out after {self._timeout_seconds:.0f}s.",
                )
                return
            except Exception as exc:  # provider crashed — surface as a failure
                logger.warning("Analysis run %s failed: %s", run_id, exc)
                await self._fail(run_id, str(exc)[:500])
                return

            # 3) Completed.
            await self._complete(run_id)
        except Exception:
            logger.exception("Analysis run %s crashed in the background task", run_id)
            # Best-effort: surface the crash as a failed run rather than
            # leaving it stuck in RUNNING forever.
            try:
                await self._fail(run_id, "internal error during execution")
            except Exception:
                logger.exception("Failed to mark crashed run %s as failed", run_id)
        finally:
            self._cancel_events.pop(run_id, None)

    # ── State transitions ───────────────────────────────────────────────
    async def _transition(
        self,
        run_id: uuid.UUID,
        new_status: AnalysisRunStatus,
        *,
        failure_reason: str | None = None,
    ) -> None:
        """Apply a validated state transition in its own session.

        The transition guard re-reads the current status, so a cancelled or
        completed run can never be clobbered by a late background write.
        """
        async with self._session_factory() as session:
            runs = AnalysisRunRepository(session)
            run = await runs.get(run_id)
            if run is None:
                raise NotFoundError("Analysis run not found.")
            allowed = _ALLOWED_FROM[new_status]
            if run.status not in allowed:
                raise ConflictError(
                    f"Cannot move analysis from {run.status.value} to {new_status.value}.",
                    code="analysis_invalid_transition",
                )

            now = datetime.now(UTC)
            if new_status is AnalysisRunStatus.RUNNING:
                run.started_at = now
            elif new_status in _TERMINAL:
                run.completed_at = now
                if run.started_at is not None:
                    run.duration_ms = _elapsed_ms(run.started_at, now)
            if failure_reason is not None:
                run.failure_reason = failure_reason[:512]
            run.status = new_status
            await self._sync_repository_status(session, run, new_status)
            await session.commit()

    async def _complete(self, run_id: uuid.UUID) -> None:
        try:
            await self._transition(run_id, AnalysisRunStatus.COMPLETED)
        except ConflictError:
            logger.info("Run %s already left RUNNING; not marking completed", run_id)

    async def _fail(self, run_id: uuid.UUID, reason: str) -> None:
        try:
            await self._transition(run_id, AnalysisRunStatus.FAILED, failure_reason=reason)
        except ConflictError:
            logger.info("Run %s already left RUNNING; not marking failed", run_id)

    async def _load_with_name(self, run_id: uuid.UUID) -> tuple[AnalysisRun, str | None] | None:
        async with self._session_factory() as session:
            return await AnalysisRunRepository(session).get_with_name(run_id)

    # ── Repository lifecycle mirror ─────────────────────────────────────
    @staticmethod
    async def _sync_repository_status(
        session: AsyncSession,
        run: AnalysisRun,
        run_status: AnalysisRunStatus,
    ) -> None:
        """Mirror the run state onto the repository's latest-analysis fields.

        A repository deleted while its run is in flight is skipped silently.
        """
        repository = await session.get(Repository, run.repository_id)
        if repository is None:
            return
        repository.analysis_status = _REPOSITORY_STATUS[run_status]
        if run_status is AnalysisRunStatus.COMPLETED:
            repository.last_analysis_at = run.completed_at
            repository.last_analysis_job_id = str(run.id)


def _elapsed_ms(started_at: datetime, ended_at: datetime) -> int:
    """Milliseconds between two timestamps, tolerating naive DB values.

    SQLite returns naive datetimes even for `DateTime(timezone=True)` columns
    (it has no timezone support), while `datetime.now(UTC)` is aware — so
    coerce both sides to UTC before subtracting.
    """

    def _utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    return max(0, int((_utc(ended_at) - _utc(started_at)).total_seconds() * 1000))
