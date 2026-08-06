"""Analysis endpoints — the Sprint 4A orchestration surface.

Every endpoint operates on `AnalysisRun` records only: start a run for a
repository, list history (globally or per repository), view one run, cancel a
queued/running run, and delete a terminal run. No scanner executes here — the
orchestrator dispatches the configured (fake) provider in the background.

Two routers are exported because the endpoints live under two URL shapes:
`/repositories/{id}/analysis` and `/analysis[/{id}]`. Both are mounted by the
aggregate router (see app/api/router.py).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_analysis_orchestrator, get_current_user
from app.domains.analysis.orchestrator import AnalysisOrchestrator
from app.domains.analysis.schemas import (
    AnalysisRunCancelResponse,
    AnalysisRunCreateResponse,
    AnalysisRunListResponse,
    AnalysisRunRead,
)
from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.user import User

analysis_router = APIRouter(prefix="/analysis", tags=["analysis"])
repo_analysis_router = APIRouter(prefix="/repositories", tags=["analysis"])

OrchestratorDep = Annotated[AnalysisOrchestrator, Depends(get_analysis_orchestrator)]
UserDep = Annotated[User, Depends(get_current_user)]


def _read(run: AnalysisRun, full_name: str | None) -> AnalysisRunRead:
    """Map a run + its repository name onto the wire contract."""
    data = AnalysisRunRead.model_validate(run).model_dump()
    data["repository_full_name"] = full_name
    return AnalysisRunRead(**data)


def _page_response(
    items: list[tuple[AnalysisRun, str]],
    total: int,
    page: int,
    page_size: int,
) -> AnalysisRunListResponse:
    total_pages = max(1, -(-total // page_size)) if total else 0
    return AnalysisRunListResponse(
        items=[_read(run, name) for run, name in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


# ── Repository-scoped ───────────────────────────────────────────────────
@repo_analysis_router.post(
    "/{repository_id}/analysis",
    response_model=AnalysisRunCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an analysis run for a repository",
)
async def start_repository_analysis(
    user: UserDep,
    orchestrator: OrchestratorDep,
    repository_id: uuid.UUID,
) -> AnalysisRunCreateResponse:
    """Queue a new run. 409 when the repository already has an active run."""
    run, full_name = await orchestrator.start(repository_id, user.id)
    return AnalysisRunCreateResponse(run=_read(run, full_name))


@repo_analysis_router.get(
    "/{repository_id}/analysis",
    response_model=AnalysisRunListResponse,
    summary="List analysis runs for one repository",
)
async def list_repository_analysis(
    user: UserDep,
    orchestrator: OrchestratorDep,
    repository_id: uuid.UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[AnalysisRunStatus | None, Query()] = None,
) -> AnalysisRunListResponse:
    items, total = await orchestrator.list(
        user.id,
        page=page,
        page_size=page_size,
        repository_id=repository_id,
        status=status,
    )
    return _page_response(items, total, page, page_size)


# ── Analysis-scoped ─────────────────────────────────────────────────────
@analysis_router.get(
    "",
    response_model=AnalysisRunListResponse,
    summary="List analysis runs",
)
async def list_analysis(
    user: UserDep,
    orchestrator: OrchestratorDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    repository_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[AnalysisRunStatus | None, Query()] = None,
) -> AnalysisRunListResponse:
    """List the user's runs, newest first, with optional repo/status filters."""
    items, total = await orchestrator.list(
        user.id,
        page=page,
        page_size=page_size,
        repository_id=repository_id,
        status=status,
    )
    return _page_response(items, total, page, page_size)


@analysis_router.get(
    "/{analysis_id}",
    response_model=AnalysisRunRead,
    summary="Get one analysis run",
)
async def get_analysis(
    user: UserDep,
    orchestrator: OrchestratorDep,
    analysis_id: uuid.UUID,
) -> AnalysisRunRead:
    run, full_name = await orchestrator.get(user.id, analysis_id)
    return _read(run, full_name)


@analysis_router.post(
    "/{analysis_id}/cancel",
    response_model=AnalysisRunCancelResponse,
    summary="Cancel an analysis run",
)
async def cancel_analysis(
    user: UserDep,
    orchestrator: OrchestratorDep,
    analysis_id: uuid.UUID,
) -> AnalysisRunCancelResponse:
    """Cancel a queued or running run. Terminal runs return 409."""
    run, full_name = await orchestrator.cancel(user.id, analysis_id)
    return AnalysisRunCancelResponse(run=_read(run, full_name))


@analysis_router.delete(
    "/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a terminal analysis run",
)
async def delete_analysis(
    user: UserDep,
    orchestrator: OrchestratorDep,
    analysis_id: uuid.UUID,
) -> Response:
    """Delete a completed/failed/cancelled run. Active runs return 409."""
    await orchestrator.delete(user.id, analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
