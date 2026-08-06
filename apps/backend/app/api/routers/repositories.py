"""Repository management endpoints — the Sprint 3A HTTP surface.

The router adapts the github domain to REST. Every endpoint requires an
authenticated user and is scoped to that user's repositories. Endpoint
ordering matters: `/repositories/search` must be declared before
`/repositories/{repository_id}` so the literal path isn't swallowed by the
parameter route.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user, get_repository_service
from app.domains.github.schemas import (
    GitHubRepositoryCandidate,
    GitHubSearchResponse,
    RepositoryImportRequest,
    RepositoryImportResponse,
    RepositoryListResponse,
    RepositoryRead,
    RepositorySyncResponse,
)
from app.domains.github.service import RepositoryService
from app.models.repository import AnalysisStatus
from app.models.user import User

router = APIRouter()

RepoService = Annotated[RepositoryService, Depends(get_repository_service)]
SearchQuery = Annotated[
    str | None, Query(max_length=256, description="Filter by name or description")
]
SearchPage = Annotated[int, Query(ge=1)]
SearchPerPage = Annotated[int, Query(ge=1, le=100)]
ListSearch = Annotated[
    str | None, Query(max_length=256, description="Search name / owner / description")
]


@router.get("/search", response_model=GitHubSearchResponse, summary="Browse GitHub repositories")
async def search_github_repositories(
    user: Annotated[User, Depends(get_current_user)],
    service: RepoService,
    q: SearchQuery = None,
    page: SearchPage = 1,
    per_page: SearchPerPage = 30,
) -> GitHubSearchResponse:
    """List the user's GitHub repositories for the import dialog."""
    items, has_more = await service.search_github_repositories(
        user.id,
        query=q,
        page=page,
        per_page=per_page,
    )
    return GitHubSearchResponse(
        items=[
            GitHubRepositoryCandidate(
                provider_repo_id=item.provider_repo_id,
                full_name=item.full_name,
                name=item.name,
                description=item.description,
                language=item.language,
                stars=item.stars,
                is_private=item.private,
                html_url=item.html_url,
                pushed_at=item.pushed_at,
            )
            for item in items
        ],
        page=page,
        has_more=has_more,
    )


@router.get("", response_model=RepositoryListResponse, summary="List tracked repositories")
async def list_repositories(
    user: Annotated[User, Depends(get_current_user)],
    service: RepoService,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: ListSearch = None,
    language: Annotated[str | None, Query(max_length=64)] = None,
    visibility: Annotated[Literal["public", "private"] | None, Query()] = None,
    status: Annotated[AnalysisStatus | None, Query(alias="analysis_status")] = None,
    archived: Annotated[bool | None, Query()] = None,
    disabled: Annotated[bool | None, Query()] = None,
    imported_after: Annotated[datetime | None, Query()] = None,
    sort: Literal[
        "name", "stars", "forks", "language", "size_kb", "pushed_at", "created_at", "updated_at"
    ] = "updated_at",
    order: Literal["asc", "desc"] = "desc",
) -> RepositoryListResponse:
    """List the authenticated user's repositories with pagination and filters."""
    items, total = await service.list_repositories(
        user.id,
        page=page,
        page_size=page_size,
        search=q,
        language=language,
        visibility=visibility,
        status=status,
        archived=archived,
        disabled=disabled,
        imported_after=imported_after,
        sort=sort,
        order=order,
    )
    total_pages = max(1, -(-total // page_size)) if total else 0
    return RepositoryListResponse(
        items=[RepositoryRead.model_validate(repo) for repo in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get(
    "/{repository_id}",
    response_model=RepositoryRead,
    summary="Get a tracked repository",
)
async def get_repository(
    user: Annotated[User, Depends(get_current_user)],
    service: RepoService,
    repository_id: uuid.UUID,
) -> RepositoryRead:
    repo = await service.get_repository(user.id, repository_id)
    return RepositoryRead.model_validate(repo)


@router.post(
    "/import",
    response_model=RepositoryImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a GitHub repository",
)
async def import_repository(
    user: Annotated[User, Depends(get_current_user)],
    service: RepoService,
    payload: RepositoryImportRequest,
    response: Response,
) -> RepositoryImportResponse:
    """Track a GitHub repository. Idempotent: re-importing refreshes it."""
    repo, was_already_imported = await service.import_repository(user.id, payload.full_name)
    # 201 on first import; 200 when the repository was already tracked.
    if was_already_imported:
        response.status_code = status.HTTP_200_OK
    return RepositoryImportResponse(
        repository=RepositoryRead.model_validate(repo),
        was_already_imported=was_already_imported,
    )


@router.patch(
    "/{repository_id}/sync",
    response_model=RepositorySyncResponse,
    summary="Refresh repository metadata from GitHub",
)
async def sync_repository(
    user: Annotated[User, Depends(get_current_user)],
    service: RepoService,
    repository_id: uuid.UUID,
) -> RepositorySyncResponse:
    repo, warning = await service.sync_repository(user.id, repository_id)
    return RepositorySyncResponse(
        repository=RepositoryRead.model_validate(repo),
        warning=warning,
    )


@router.delete(
    "/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a repository from EvoShield",
)
async def delete_repository(
    user: Annotated[User, Depends(get_current_user)],
    service: RepoService,
    repository_id: uuid.UUID,
) -> Response:
    """Untrack a repository (the upstream GitHub repo is untouched)."""
    await service.delete_repository(user.id, repository_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
