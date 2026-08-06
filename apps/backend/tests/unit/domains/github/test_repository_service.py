"""Unit tests for the repository integration service.

`RepositoryService` is exercised with a real (per-test reset) database
session but **fake** token provider and GitHub client, so every business
rule is verified without a network call: idempotent import, sync semantics
(including deleted-upstream), deletion, user scoping, and the
not-connected error path.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.db.session import session_factory
from app.domains.github.ports import GitHubRepoData
from app.domains.github.service import RepositoryService
from app.models.repository import AnalysisStatus, Repository
from app.models.user import User


def _repo_data(full_name: str, **overrides) -> GitHubRepoData:
    defaults: dict = dict(
        provider_repo_id="1296269",
        name=full_name.split("/")[-1],
        full_name=full_name,
        html_url=f"https://github.com/{full_name}",
        description=f"Repo {full_name}",
        private=False,
        language="Python",
        default_branch="main",
        stars=42,
        forks=7,
        open_issues=3,
        topics=("demo",),
        license_spdx="MIT",
        size_kb=185,
        archived=False,
        disabled=False,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
        pushed_at=datetime(2024, 3, 1, tzinfo=UTC),
    )
    defaults.update(overrides)
    return GitHubRepoData(**defaults)


class FakeGitHubClient:
    """Stands in for `GitHubAPIClient` behind the GitHubRepoProvider port."""

    def __init__(self) -> None:
        self.repos: dict[str, GitHubRepoData] = {}
        self.raise_error: Exception | None = None

    async def get_repository(self, full_name: str) -> GitHubRepoData:
        if self.raise_error is not None:
            raise self.raise_error
        try:
            return self.repos[full_name]
        except KeyError:
            raise NotFoundError("This repository does not exist on GitHub.") from None

    async def list_user_repositories(
        self, *, page: int = 1, per_page: int = 30, query: str | None = None
    ) -> list[GitHubRepoData]:
        return list(self.repos.values())


class FakeTokenProvider:
    """Returns a fixed token, or None to simulate a disconnected account."""

    def __init__(self, token: str | None = "ghp_test") -> None:
        self.token = token

    async def get_access_token(self, user_id: uuid.UUID, provider: str = "github") -> str | None:
        return self.token


async def _new_user(session, email: str | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email or f"svc-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Service Tester",
        auth_provider="local",
    )
    session.add(user)
    await session.flush()
    return user


def _service(session, fake: FakeGitHubClient, token: str | None = "ghp_test") -> RepositoryService:
    return RepositoryService(
        session=session,
        token_provider=FakeTokenProvider(token),
        client_factory=lambda access_token: fake,
    )


def test_import_creates_repository_row() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)
            fake = FakeGitHubClient()
            fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")

            repo, was_already = await _service(session, fake).import_repository(
                user.id, "octocat/Hello-World"
            )
            assert was_already is False
            assert repo.full_name == "octocat/Hello-World"
            assert repo.owner_id == user.id
            assert repo.provider == "github"
            assert repo.analysis_status is AnalysisStatus.NOT_ANALYZED
            assert repo.stars == 42
            assert repo.topics == ["demo"]
            assert repo.last_synced_at is not None

    asyncio.run(scenario())


def test_reimport_is_idempotent_and_refreshes_metadata() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)
            fake = FakeGitHubClient()
            fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World", stars=42)

            service = _service(session, fake)
            first, was_already = await service.import_repository(user.id, "octocat/Hello-World")
            assert was_already is False

            # Upstream grows; re-importing must refresh, not duplicate.
            fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World", stars=99)
            second, was_already = await service.import_repository(user.id, "octocat/Hello-World")
            assert was_already is True
            assert second.id == first.id
            assert second.stars == 99

            rows = (await session.execute(select(Repository))).scalars().all()
            assert len(rows) == 1

    asyncio.run(scenario())


def test_import_requires_connected_github_account() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)
            fake = FakeGitHubClient()
            fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")

            with pytest.raises(UnauthorizedError) as excinfo:
                await _service(session, fake, token=None).import_repository(
                    user.id, "octocat/Hello-World"
                )
            assert excinfo.value.code == "github_not_connected"

    asyncio.run(scenario())


def test_sync_refreshes_metadata_without_reimport() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)
            fake = FakeGitHubClient()
            fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World", stars=10)

            service = _service(session, fake)
            repo, _ = await service.import_repository(user.id, "octocat/Hello-World")
            repo_id = repo.id

            fake.repos["octocat/Hello-World"] = _repo_data(
                "octocat/Hello-World", stars=500, description="Updated description"
            )
            synced, warning = await service.sync_repository(user.id, repo_id)
            assert warning is None
            assert synced.stars == 500
            assert synced.description == "Updated description"
            assert synced.last_synced_at is not None
            assert synced.is_active is True

    asyncio.run(scenario())


def test_sync_of_deleted_upstream_marks_inactive_with_warning() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)
            fake = FakeGitHubClient()
            fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")

            service = _service(session, fake)
            repo, _ = await service.import_repository(user.id, "octocat/Hello-World")
            repo_id = repo.id

            # The repository vanishes upstream (GitHub 404).
            del fake.repos["octocat/Hello-World"]
            synced, warning = await service.sync_repository(user.id, repo_id)
            assert warning is not None
            assert synced.is_active is False
            # Row is kept — history is not orphaned.
            fetched = await service.get_repository(user.id, repo_id)
            assert fetched.id == repo_id

    asyncio.run(scenario())


def test_repositories_are_scoped_per_user() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            alice = await _new_user(session, email="alice@example.com")
            bob = await _new_user(session, email="bob@example.com")
            fake = FakeGitHubClient()
            fake.repos["alice/private-repo"] = _repo_data("alice/private-repo")

            service = _service(session, fake)
            repo, _ = await service.import_repository(alice.id, "alice/private-repo")

            # Bob cannot see or touch Alice's repository.
            with pytest.raises(NotFoundError):
                await service.get_repository(bob.id, repo.id)
            alice_rows, alice_total = await service.list_repositories(
                alice.id,
                page=1,
                page_size=20,
                search=None,
                language=None,
                visibility=None,
                status=None,
                sort="updated_at",
                order="desc",
            )
            bob_rows, bob_total = await service.list_repositories(
                bob.id,
                page=1,
                page_size=20,
                search=None,
                language=None,
                visibility=None,
                status=None,
                sort="updated_at",
                order="desc",
            )
            assert alice_total == 1 and len(alice_rows) == 1
            assert bob_total == 0 and len(bob_rows) == 0

    asyncio.run(scenario())


def test_delete_removes_repository() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            user = await _new_user(session)
            fake = FakeGitHubClient()
            fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")

            service = _service(session, fake)
            repo, _ = await service.import_repository(user.id, "octocat/Hello-World")

            await service.delete_repository(user.id, repo.id)
            with pytest.raises(NotFoundError):
                await service.get_repository(user.id, repo.id)

    asyncio.run(scenario())
