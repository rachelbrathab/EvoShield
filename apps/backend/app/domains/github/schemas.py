"""Github domain API contracts.

The source-provider domain owns the repository contract. `RepositoryRead`
is the wire shape for tracked repositories — the analysis-status trio from
Sprint 3 preparation plus the GitHub metadata Sprint 3A ingestion writes.
All new fields are optional/defaulted so the contract stays backward
compatible with earlier clients.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.repository import AnalysisStatus


class RepositoryRead(BaseModel):
    """API contract for a tracked repository."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    provider: str
    provider_repo_id: str | None = None
    name: str
    full_name: str
    default_branch: str | None = None
    html_url: str | None = None
    description: str | None = None
    is_private: bool = False
    is_active: bool = True

    # GitHub metadata (Sprint 3A)
    language: str | None = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    topics: list[str] = Field(default_factory=list)
    license: str | None = None
    size_kb: int | None = None
    archived: bool = False
    disabled: bool = False
    provider_created_at: datetime | None = None
    provider_updated_at: datetime | None = None
    pushed_at: datetime | None = None
    last_synced_at: datetime | None = None

    # Analysis status — Sprint 4/5 pipelines transition this lifecycle state.
    analysis_status: AnalysisStatus
    last_analysis_at: datetime | None = None
    last_analysis_job_id: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None


class RepositoryListResponse(BaseModel):
    """Paginated, filterable list of tracked repositories."""

    items: list[RepositoryRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class RepositoryImportRequest(BaseModel):
    """Import a repository by its GitHub ``owner/name``."""

    full_name: str = Field(
        min_length=3,
        max_length=512,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        description="GitHub repository in `owner/name` form, e.g. `octocat/Hello-World`",
    )


class RepositoryImportResponse(BaseModel):
    """Result of an import — idempotent by design."""

    repository: RepositoryRead
    was_already_imported: bool


class RepositorySyncResponse(BaseModel):
    """Result of a metadata refresh."""

    repository: RepositoryRead
    warning: str | None = None


class GitHubRepositoryCandidate(BaseModel):
    """A GitHub repository offered in the import browser."""

    provider_repo_id: str
    full_name: str
    name: str
    description: str | None = None
    language: str | None = None
    stars: int = 0
    is_private: bool = False
    html_url: str
    pushed_at: datetime | None = None


class GitHubSearchResponse(BaseModel):
    """A page of GitHub repositories the user can import."""

    items: list[GitHubRepositoryCandidate]
    page: int
    has_more: bool
