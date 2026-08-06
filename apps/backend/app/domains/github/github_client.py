"""GitHub REST API client — the GitHub adapter behind the source-provider port.

Every GitHub-specific detail lives here: endpoint URLs, header format, JSON
payload shape, rate-limit headers, error mapping. The domain service only
ever sees `GitHubRepoData` objects through the `GitHubRepoProvider` port, so
a GitLab/Bitbucket adapter can replace this class without touching business
logic (see `ports.py`).

Errors are translated into the application exception taxonomy so the HTTP
layer stays uniform:

- 401        → `UnauthorizedError` (token invalid/expired → reconnect)
- 403 + rate → `ProviderError` status 429 (rate limit, with reset hint)
- 404        → `NotFoundError` (repo missing or deleted upstream)
- 5xx/network → `ProviderError` status 502 (GitHub unavailable)
"""

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ProviderError, UnauthorizedError
from app.domains.github.ports import GitHubRepoData, GitHubRepoProvider

logger = logging.getLogger(__name__)

_API_VERSION = "2022-11-28"


class GitHubAPIClient(GitHubRepoProvider):
    """Stateless REST client; construct per user (token) via the factory."""

    def __init__(
        self,
        access_token: str,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
    ) -> None:
        self._base_url = (base_url or get_settings().github_api_url).rstrip("/")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
        }
        self._client = client or httpx.AsyncClient(timeout=15, headers=headers)
        if client is not None:
            self._client.headers.update(headers)

    # ── Port implementation ─────────────────────────────────────────────
    async def get_repository(self, full_name: str) -> GitHubRepoData:
        payload = await self._request("GET", f"/repos/{full_name.lstrip('/')}")
        return self._normalize(payload)

    async def list_user_repositories(
        self,
        *,
        page: int = 1,
        per_page: int = 30,
        query: str | None = None,
    ) -> list[GitHubRepoData]:
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "sort": "updated",
        }
        payloads = await self._request("GET", "/user/repos", params=params)
        items = [self._normalize(item) for item in payloads]
        if query:
            needle = query.casefold()
            items = [
                repo
                for repo in items
                if needle in repo.full_name.casefold()
                or (repo.description and needle in repo.description.casefold())
            ]
        return items

    # ── Plumbing ────────────────────────────────────────────────────────
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            response = await self._client.request(method, url, params=params)
        except httpx.HTTPError as exc:
            logger.warning("GitHub request failed: %s %s (%s)", method, path, exc)
            raise ProviderError(
                "GitHub API is unavailable — check your connection and try again.",
                status_code=502,
            ) from exc
        self._raise_for_status(response, method, path)
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("GitHub returned an invalid response.") from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response, method: str, path: str) -> None:
        if response.status_code < 400:
            return
        logger.warning("GitHub error %s on %s %s", response.status_code, method, path)

        if response.status_code == 401:
            raise UnauthorizedError(
                "Your GitHub connection is invalid or expired — reconnect your account.",
                code="github_token_invalid",
            )
        if response.status_code == 404:
            raise NotFoundError("This repository does not exist on GitHub.")
        if response.status_code == 403:
            if response.headers.get("x-ratelimit-remaining") == "0":
                raise ProviderError(
                    "GitHub API rate limit exceeded — wait a minute and try again.",
                    status_code=429,
                    code="github_rate_limited",
                )
            raise ProviderError(
                "GitHub refused this request (403).",
                status_code=403,
                code="github_forbidden",
            )
        if response.status_code >= 500:
            raise ProviderError(
                "GitHub is having issues — try again shortly.",
                status_code=502,
            )
        raise ProviderError(
            f"GitHub request failed with status {response.status_code}.",
        )

    # ── Normalization ───────────────────────────────────────────────────
    @staticmethod
    def _normalize(payload: dict[str, Any]) -> GitHubRepoData:
        """Map the GitHub REST payload onto the provider-agnostic shape."""
        license_info = payload.get("license") or {}
        return GitHubRepoData(
            provider_repo_id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            full_name=str(payload.get("full_name", "")),
            html_url=str(payload.get("html_url", "")),
            description=payload.get("description"),
            private=bool(payload.get("private", False)),
            language=payload.get("language"),
            default_branch=payload.get("default_branch"),
            stars=int(payload.get("stargazers_count", 0) or 0),
            forks=int(payload.get("forks_count", 0) or 0),
            open_issues=int(payload.get("open_issues_count", 0) or 0),
            topics=tuple(str(topic) for topic in (payload.get("topics") or [])),
            license_spdx=license_info.get("spdx_id"),
            size_kb=int(payload.get("size", 0) or 0),
            archived=bool(payload.get("archived", False)),
            disabled=bool(payload.get("disabled", False)),
            created_at=GitHubAPIClient._parse_datetime(payload.get("created_at")),
            updated_at=GitHubAPIClient._parse_datetime(payload.get("updated_at")),
            pushed_at=GitHubAPIClient._parse_datetime(payload.get("pushed_at")),
        )

    @staticmethod
    def _parse_datetime(value: str | None) -> Any:
        """Parse GitHub's ISO-8601 timestamps (``2024-01-01T00:00:00Z``)."""
        from datetime import datetime

        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Unparseable GitHub timestamp: %r", value)
            return None
