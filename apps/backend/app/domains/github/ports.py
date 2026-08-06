"""Source-provider domain ports (Sprint 3A).

The `github` domain owns repository ingestion for *any* source provider.
`GitHubRepoProvider` is the port the service depends on; `GitHubAPIClient`
(in `github_client.py`) is the GitHub adapter implementing it. Adding
GitLab/Bitbucket/Azure DevOps later means a new adapter implementing the
same port — no downstream domain changes (see docs/module-dependency.md).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class GitHubRepoData:
    """Normalized repository payload returned by a source provider.

    Field names are provider-agnostic (a GitLab adapter maps its own fields
    onto this shape), so the service and the ORM never see provider detail.
    """

    provider_repo_id: str
    name: str
    full_name: str
    html_url: str
    description: str | None
    private: bool
    language: str | None
    default_branch: str | None
    stars: int
    forks: int
    open_issues: int
    topics: tuple[str, ...]
    license_spdx: str | None
    size_kb: int
    archived: bool
    disabled: bool
    created_at: datetime | None
    updated_at: datetime | None
    pushed_at: datetime | None


class GitHubRepoProvider(Protocol):
    """Port every source-provider adapter implements."""

    async def get_repository(self, full_name: str) -> GitHubRepoData:
        """Fetch one repository by its ``owner/name``."""
        ...

    async def list_user_repositories(
        self,
        *,
        page: int = 1,
        per_page: int = 30,
        query: str | None = None,
    ) -> list[GitHubRepoData]:
        """List repositories the authenticated user can access (browse flow)."""
        ...


class GitHubClientFactory(Protocol):
    """Builds a provider client bound to one user's access token."""

    def __call__(self, access_token: str) -> GitHubRepoProvider:
        """Return a client authenticated as the token's owner."""
        ...


class AccessTokenProvider(Protocol):
    """Resolves the stored upstream access token for a user."""

    async def get_access_token(self, user_id: uuid.UUID, provider: str = "github") -> str | None:
        """Return the token, or None when the user has not connected the provider."""
        ...
