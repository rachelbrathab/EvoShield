"""Github domain business logic — repository integration services.

`RepositoryService` owns the application rules for repository management:

- **Import** is an idempotent upsert: a repo the user already tracks is
  re-synced, never duplicated (the `(owner_id, full_name)` natural key).
- **Sync** refreshes metadata from the provider without re-importing; a repo
  that vanished upstream is marked inactive with a warning, never deleted.
- **Delete** removes the EvoShield row (the upstream repo is untouched).
- Every query is scoped to the authenticated user.

The service depends on ports (`GitHubRepoProvider` via a client factory,
`AccessTokenProvider`) — never on the concrete GitHub client — so tests
inject fakes and GitLab/Bitbucket can be added as sibling providers.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.domains.github.github_client import GitHubAPIClient
from app.domains.github.ports import (
    AccessTokenProvider,
    GitHubClientFactory,
    GitHubRepoData,
    GitHubRepoProvider,
)
from app.domains.github.repository import RepositoryRepository
from app.models.repository import AnalysisStatus, Repository

logger = logging.getLogger(__name__)

_GITHUB_PROVIDER = "github"


class RepositoryService:
    """Facade over repository import, sync, query and deletion."""

    def __init__(
        self,
        session: AsyncSession,
        token_provider: AccessTokenProvider,
        client_factory: GitHubClientFactory | None = None,
    ) -> None:
        self._session = session
        self._repos = RepositoryRepository(session)
        self._tokens = token_provider
        self._client_factory: GitHubClientFactory = client_factory or (
            lambda access_token: GitHubAPIClient(access_token=access_token)
        )

    # ── Public API ──────────────────────────────────────────────────────
    async def import_repository(
        self, user_id: uuid.UUID, full_name: str
    ) -> tuple[Repository, bool]:
        """Track a repository. Returns (repo, was_already_imported)."""
        client = await self._client_for(user_id)
        data = await client.get_repository(full_name)

        existing = await self._repos.get_by_full_name(user_id, data.full_name)
        if existing is not None:
            self._apply_github_data(existing, data)
            existing.last_synced_at = datetime.now(UTC)
            await self._session.commit()
            # `updated_at` is server-computed (onupdate=func.now()) and expires
            # after commit; refresh so attribute access (e.g. Pydantic
            # serialization) never triggers a lazy load outside the event loop.
            await self._session.refresh(existing)
            return existing, True

        repo = Repository(
            owner_id=user_id,
            provider=_GITHUB_PROVIDER,
            analysis_status=AnalysisStatus.NOT_ANALYZED,
        )
        self._apply_github_data(repo, data)
        repo.last_synced_at = datetime.now(UTC)
        self._session.add(repo)
        try:
            await self._session.commit()
        except IntegrityError:
            # Concurrent duplicate import (double-click, retry, second tab):
            # the unique (owner_id, full_name) constraint fired. Roll back and
            # treat it as a re-import instead of surfacing a 500.
            await self._session.rollback()
            existing = await self._repos.get_by_full_name(user_id, data.full_name)
            if existing is None:
                raise
            self._apply_github_data(existing, data)
            existing.last_synced_at = datetime.now(UTC)
            await self._session.commit()
            await self._session.refresh(existing)
            return existing, True
        await self._session.refresh(repo)
        return repo, False

    async def sync_repository(
        self, user_id: uuid.UUID, repository_id: uuid.UUID
    ) -> tuple[Repository, str | None]:
        """Refresh a tracked repository from the provider.

        Returns (repo, warning). A repository that no longer exists upstream
        is kept but marked inactive, with a human-readable warning.
        """
        repo = await self._get_owned(user_id, repository_id)
        client = await self._client_for(user_id)
        try:
            data = await client.get_repository(repo.full_name)
        except NotFoundError:
            # Deleted upstream — keep the row so history isn't orphaned, but
            # flag it inactive so the UI can surface the state.
            repo.is_active = False
            repo.last_synced_at = datetime.now(UTC)
            await self._session.commit()
            await self._session.refresh(repo)
            logger.info("Repository %s no longer exists on GitHub; marked inactive", repo.full_name)
            return repo, "This repository no longer exists on GitHub — it has been marked inactive."

        self._apply_github_data(repo, data)
        repo.is_active = True
        repo.last_synced_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(repo)
        return repo, None

    async def get_repository(self, user_id: uuid.UUID, repository_id: uuid.UUID) -> Repository:
        return await self._get_owned(user_id, repository_id)

    async def list_repositories(
        self,
        user_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        language: str | None,
        visibility: str | None,
        status: AnalysisStatus | None,
        sort: str,
        order: str,
    ) -> tuple[list[Repository], int]:
        rows, total = await self._repos.list(
            user_id,
            page=page,
            page_size=page_size,
            search=search,
            language=language,
            visibility=visibility,
            status=status,
            sort=sort,
            order=order,
        )
        return list(rows), total

    async def delete_repository(self, user_id: uuid.UUID, repository_id: uuid.UUID) -> None:
        repo = await self._get_owned(user_id, repository_id)
        await self._repos.delete(repo)
        await self._session.commit()

    async def search_github_repositories(
        self,
        user_id: uuid.UUID,
        *,
        query: str | None,
        page: int,
        per_page: int,
    ) -> tuple[list[GitHubRepoData], bool]:
        """Browse the user's GitHub repositories (the import dialog).

        Returns (items, has_more). `query` filters locally across the fetched
        page; pagination follows the provider's pages.
        """
        client = await self._client_for(user_id)
        items = await client.list_user_repositories(page=page, per_page=per_page, query=query)
        return items, len(items) >= per_page

    # ── Internal helpers ────────────────────────────────────────────────
    async def _get_owned(self, user_id: uuid.UUID, repository_id: uuid.UUID) -> Repository:
        repo = await self._repos.get_for_owner(user_id, repository_id)
        if repo is None:
            raise NotFoundError("Repository not found.")
        return repo

    async def _client_for(self, user_id: uuid.UUID) -> GitHubRepoProvider:
        token = await self._tokens.get_access_token(user_id, _GITHUB_PROVIDER)
        if not token:
            raise UnauthorizedError(
                "Connect your GitHub account to manage repositories.",
                code="github_not_connected",
            )
        return self._client_factory(token)

    @staticmethod
    def _apply_github_data(repo: Repository, data: GitHubRepoData) -> None:
        """Copy normalized provider metadata onto the repository aggregate."""
        repo.provider_repo_id = data.provider_repo_id
        repo.name = data.name
        repo.full_name = data.full_name
        repo.html_url = data.html_url
        repo.description = data.description
        repo.is_private = data.private
        repo.language = data.language
        repo.default_branch = data.default_branch
        repo.stars = data.stars
        repo.forks = data.forks
        repo.open_issues = data.open_issues
        repo.topics = list(data.topics)
        repo.license = data.license_spdx
        repo.size_kb = data.size_kb
        repo.archived = data.archived
        repo.disabled = data.disabled
        repo.provider_created_at = data.created_at
        repo.provider_updated_at = data.updated_at
        repo.pushed_at = data.pushed_at
