"""Integration tests for the repository management API.

Runs against the real FastAPI app + test database. The `get_repository_service`
dependency is overridden with a service backed by a fake GitHub client, so the
full HTTP → service → DB path is exercised without network calls. The fake is
replaced per test via `app.dependency_overrides`.
"""

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_repository_service
from app.core.exceptions import NotFoundError
from app.db.session import session_factory
from app.domains.github.ports import GitHubRepoData
from app.domains.github.service import RepositoryService
from app.main import app

REGISTER_PAYLOAD = {
    "email": "repo-admin@example.com",
    "password": "correct-horse-battery",
    "full_name": "Repo Admin",
}


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
    """Implements the GitHubRepoProvider port with in-memory state."""

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
        items = list(self.repos.values())
        if query:
            needle = query.casefold()
            items = [
                repo
                for repo in items
                if needle in repo.full_name.casefold()
                or (repo.description and needle in repo.description.casefold())
            ]
        return items


class FakeTokenProvider:
    def __init__(self, token: str | None = "ghp_test") -> None:
        self.token = token

    async def get_access_token(self, user_id: uuid.UUID, provider: str = "github") -> str | None:
        return self.token


# The active fake, swapped per test.
_active_fake = FakeGitHubClient()
_active_token: str | None = "ghp_test"


def _install_override() -> None:
    """Point `get_repository_service` at a service with the active fake."""

    async def override() -> AsyncIterator[RepositoryService]:
        async with session_factory() as session:
            yield RepositoryService(
                session=session,
                token_provider=FakeTokenProvider(_active_token),
                client_factory=lambda access_token: _active_fake,
            )

    app.dependency_overrides[get_repository_service] = override


def _reset_fakes() -> None:
    _active_fake.repos.clear()
    _active_fake.raise_error = None
    globals()["_active_token"] = "ghp_test"


@pytest.fixture(autouse=True)
def _repo_override() -> Iterator[None]:
    _reset_fakes()
    _install_override()
    yield
    app.dependency_overrides.pop(get_repository_service, None)


def _register(client: TestClient, **overrides: str) -> None:
    payload = {**REGISTER_PAYLOAD, **overrides}
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201


def _import(client: TestClient, full_name: str):
    return client.post("/api/v1/repositories/import", json={"full_name": full_name})


# ── Auth gating ──────────────────────────────────────────────────────────
def test_repository_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/repositories").status_code == 401
    assert client.get("/api/v1/repositories/search").status_code == 401
    assert client.post("/api/v1/repositories/import", json={"full_name": "a/b"}).status_code == 401
    assert client.get(f"/api/v1/repositories/{uuid.uuid4()}").status_code == 401


def test_import_validates_full_name_format(client: TestClient) -> None:
    _register(client)
    response = client.post("/api/v1/repositories/import", json={"full_name": "not-a-full-name"})
    assert response.status_code == 422


# ── Import + list flow ───────────────────────────────────────────────────
def test_import_then_list_populates_repository(client: TestClient) -> None:
    _register(client)
    _active_fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")

    response = _import(client, "octocat/Hello-World")
    assert response.status_code == 201
    body = response.json()
    assert body["was_already_imported"] is False
    repo = body["repository"]
    assert repo["full_name"] == "octocat/Hello-World"
    assert repo["stars"] == 42
    assert repo["language"] == "Python"
    assert repo["analysis_status"] == "not_analyzed"
    assert repo["topics"] == ["demo"]

    listed = client.get("/api/v1/repositories").json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == repo["id"]
    assert listed["items"][0]["owner_id"] == repo["owner_id"]

    detail = client.get(f"/api/v1/repositories/{repo['id']}").json()
    assert detail["license"] == "MIT"
    assert detail["default_branch"] == "main"


def test_reimport_is_idempotent_and_returns_200(client: TestClient) -> None:
    _register(client)
    _active_fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World", stars=1)

    first = _import(client, "octocat/Hello-World")
    assert first.status_code == 201

    _active_fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World", stars=2)
    second = _import(client, "octocat/Hello-World")
    assert second.status_code == 200
    body = second.json()
    assert body["was_already_imported"] is True
    assert body["repository"]["stars"] == 2

    assert client.get("/api/v1/repositories").json()["total"] == 1


def test_import_missing_repository_returns_404(client: TestClient) -> None:
    _register(client)
    response = _import(client, "nobody/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_import_without_github_connection_returns_401(client: TestClient) -> None:
    _register(client)
    globals()["_active_token"] = None
    response = _import(client, "octocat/Hello-World")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "github_not_connected"


def test_search_without_github_connection_returns_401(client: TestClient) -> None:
    _register(client)
    globals()["_active_token"] = None
    response = client.get("/api/v1/repositories/search")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "github_not_connected"


# ── Sync ─────────────────────────────────────────────────────────────────
def test_sync_refreshes_metadata(client: TestClient) -> None:
    _register(client)
    _active_fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World", stars=3)
    repo = _import(client, "octocat/Hello-World").json()["repository"]

    _active_fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World", stars=777)
    response = client.patch(f"/api/v1/repositories/{repo['id']}/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["warning"] is None
    assert body["repository"]["stars"] == 777
    assert body["repository"]["last_synced_at"] is not None


def test_sync_deleted_upstream_marks_inactive(client: TestClient) -> None:
    _register(client)
    _active_fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World").json()["repository"]

    del _active_fake.repos["octocat/Hello-World"]
    response = client.patch(f"/api/v1/repositories/{repo['id']}/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["warning"] is not None
    assert body["repository"]["is_active"] is False


# ── Search (GitHub browse) ───────────────────────────────────────────────
def test_search_browses_github_repositories(client: TestClient) -> None:
    _register(client)
    _active_fake.repos = {
        "octocat/alpha": _repo_data("octocat/alpha", provider_repo_id="1"),
        "octocat/beta": _repo_data("octocat/beta", provider_repo_id="2"),
        "other/gamma": _repo_data("other/gamma", provider_repo_id="3"),
    }

    all_items = client.get("/api/v1/repositories/search").json()
    assert len(all_items["items"]) == 3

    filtered = client.get("/api/v1/repositories/search", params={"q": "beta"}).json()
    assert [i["full_name"] for i in filtered["items"]] == ["octocat/beta"]

    private = _repo_data("octocat/secret", provider_repo_id="4", private=True)
    _active_fake.repos["octocat/secret"] = private
    results = client.get("/api/v1/repositories/search", params={"q": "secret"}).json()
    assert results["items"][0]["is_private"] is True


# ── Delete ───────────────────────────────────────────────────────────────
def test_delete_untracks_repository(client: TestClient) -> None:
    _register(client)
    _active_fake.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World").json()["repository"]

    response = client.delete(f"/api/v1/repositories/{repo['id']}")
    assert response.status_code == 204
    assert client.get("/api/v1/repositories").json()["total"] == 0
    assert client.get(f"/api/v1/repositories/{repo['id']}").status_code == 404


# ── Scoping & filters ────────────────────────────────────────────────────
def test_users_never_see_each_others_repositories(client: TestClient) -> None:
    _register(client, email="alice@example.com")
    _active_fake.repos["alice/repo"] = _repo_data("alice/repo")
    repo = _import(client, "alice/repo").json()["repository"]

    _register(client, email="bob@example.com")
    assert client.get("/api/v1/repositories").json()["total"] == 0
    assert client.get(f"/api/v1/repositories/{repo['id']}").status_code == 404
    assert client.patch(f"/api/v1/repositories/{repo['id']}/sync").status_code == 404
    assert client.delete(f"/api/v1/repositories/{repo['id']}").status_code == 404


def test_list_search_filter_sort_and_pagination(client: TestClient) -> None:
    _register(client)
    _active_fake.repos = {
        "octocat/alpha": _repo_data(
            "octocat/alpha", provider_repo_id="1", language="Python", stars=5
        ),
        "octocat/beta": _repo_data(
            "octocat/beta", provider_repo_id="2", language="Go", stars=50, private=True
        ),
        "octocat/gamma": _repo_data(
            "octocat/gamma", provider_repo_id="3", language="Python", stars=500
        ),
    }
    for name in _active_fake.repos:
        _import(client, name)

    # Search
    search = client.get("/api/v1/repositories", params={"q": "beta"}).json()
    assert search["total"] == 1
    assert search["items"][0]["full_name"] == "octocat/beta"

    # Language filter
    python = client.get("/api/v1/repositories", params={"language": "Python"}).json()
    assert python["total"] == 2

    # Visibility filter
    private = client.get("/api/v1/repositories", params={"visibility": "private"}).json()
    assert private["total"] == 1
    public = client.get("/api/v1/repositories", params={"visibility": "public"}).json()
    assert public["total"] == 2

    # Sort by stars desc
    sorted_repos = client.get(
        "/api/v1/repositories", params={"sort": "stars", "order": "desc"}
    ).json()
    assert [i["stars"] for i in sorted_repos["items"]] == [500, 50, 5]

    # Pagination
    page1 = client.get("/api/v1/repositories", params={"page": 1, "page_size": 2}).json()
    page2 = client.get("/api/v1/repositories", params={"page": 2, "page_size": 2}).json()
    assert page1["total"] == 3 and page1["total_pages"] == 2
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    ids1 = {i["id"] for i in page1["items"]}
    ids2 = {i["id"] for i in page2["items"]}
    assert not (ids1 & ids2)
