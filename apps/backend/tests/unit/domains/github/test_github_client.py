"""Unit tests for the GitHub REST client — no network, no database.

The client is exercised through `httpx.MockTransport`, proving payload
normalization and the mapping of GitHub error responses onto the application
exception taxonomy (401 → Unauthorized, 404 → NotFound, rate-limit 403 →
ProviderError 429, network failure → ProviderError 502).
"""

import httpx
import pytest

from app.core.exceptions import NotFoundError, ProviderError, UnauthorizedError
from app.domains.github.github_client import GitHubAPIClient

REPO_PAYLOAD = {
    "id": 1296269,
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "html_url": "https://github.com/octocat/Hello-World",
    "description": "My first repository on GitHub!",
    "private": False,
    "fork": False,
    "language": "Python",
    "default_branch": "main",
    "stargazers_count": 42,
    "forks_count": 7,
    "open_issues_count": 3,
    "topics": ["demo", "octocat"],
    "license": {"spdx_id": "MIT"},
    "size": 185,
    "archived": False,
    "disabled": False,
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-02-01T10:00:00Z",
    "pushed_at": "2024-03-01T10:00:00Z",
}


def _client(handler) -> GitHubAPIClient:
    # httpx 0.28+ MockTransport requires an async handler for async clients.
    transport = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    )
    return GitHubAPIClient(access_token="ghp_test", client=transport)


def _json_handler(payload, status: int = 200, headers: dict[str, str] | None = None):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload, headers=headers or {})

    return handler


def test_get_repository_normalizes_payload() -> None:
    client = _client(_json_handler(REPO_PAYLOAD))

    async def scenario() -> None:
        repo = await client.get_repository("octocat/Hello-World")
        assert repo.provider_repo_id == "1296269"
        assert repo.full_name == "octocat/Hello-World"
        assert repo.name == "Hello-World"
        assert repo.description == "My first repository on GitHub!"
        assert repo.private is False
        assert repo.language == "Python"
        assert repo.default_branch == "main"
        assert repo.stars == 42
        assert repo.forks == 7
        assert repo.open_issues == 3
        assert repo.topics == ("demo", "octocat")
        assert repo.license_spdx == "MIT"
        assert repo.size_kb == 185
        assert repo.archived is False
        assert repo.disabled is False
        assert repo.created_at is not None and repo.created_at.year == 2024
        assert repo.pushed_at is not None

    import asyncio

    asyncio.run(scenario())


def test_get_repository_sends_owner_and_name() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=REPO_PAYLOAD)

    client = _client(handler)

    import asyncio

    async def scenario() -> None:
        await client.get_repository("octocat/Hello-World")
        assert captured["url"] == "https://api.github.com/repos/octocat/Hello-World"
        assert captured["auth"] == "Bearer ghp_test"

    asyncio.run(scenario())


def test_missing_repository_maps_to_not_found() -> None:
    client = _client(_json_handler({"message": "Not Found"}, status=404))

    import asyncio

    async def scenario() -> None:
        with pytest.raises(NotFoundError):
            await client.get_repository("nobody/missing")

    asyncio.run(scenario())


def test_rate_limit_maps_to_429() -> None:
    client = _client(
        _json_handler(
            {"message": "API rate limit exceeded"},
            status=403,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1700000000"},
        )
    )

    import asyncio

    async def scenario() -> None:
        with pytest.raises(ProviderError) as excinfo:
            await client.get_repository("octocat/Hello-World")
        assert excinfo.value.status_code == 429
        assert excinfo.value.code == "github_rate_limited"

    asyncio.run(scenario())


def test_invalid_token_maps_to_unauthorized() -> None:
    client = _client(_json_handler({"message": "Bad credentials"}, status=401))

    import asyncio

    async def scenario() -> None:
        with pytest.raises(UnauthorizedError) as excinfo:
            await client.get_repository("octocat/Hello-World")
        assert excinfo.value.code == "github_token_invalid"

    asyncio.run(scenario())


def test_network_failure_maps_to_provider_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(handler)

    import asyncio

    async def scenario() -> None:
        with pytest.raises(ProviderError) as excinfo:
            await client.get_repository("octocat/Hello-World")
        assert excinfo.value.status_code == 502

    asyncio.run(scenario())


def test_list_user_repositories_filters_by_query() -> None:
    payloads = [
        {**REPO_PAYLOAD, "id": 1, "full_name": "octocat/alpha", "name": "alpha"},
        {
            **REPO_PAYLOAD,
            "id": 2,
            "full_name": "octocat/beta",
            "name": "beta",
            "description": "A searchable description",
        },
        {**REPO_PAYLOAD, "id": 3, "full_name": "other/gamma", "name": "gamma"},
    ]
    client = _client(_json_handler(payloads))

    import asyncio

    async def scenario() -> None:
        all_repos = await client.list_user_repositories(page=1, per_page=30)
        assert len(all_repos) == 3
        filtered = await client.list_user_repositories(page=1, per_page=30, query="beta")
        assert [r.full_name for r in filtered] == ["octocat/beta"]
        by_desc = await client.list_user_repositories(page=1, per_page=30, query="searchable")
        assert [r.full_name for r in by_desc] == ["octocat/beta"]

    asyncio.run(scenario())
