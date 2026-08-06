"""GitHub OAuth client — the authorization-code flow.

The GitHub provider is intentionally small: exchange a code for a token and
fetch the authenticated user. OAuth is not the auth *provider* — successful
GitHub logins create a local identity via the identity service.
"""

from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.domains.identity.ports import AuthUser


class GitHubOAuthClient:
    """Minimal GitHub OAuth App client (server-side authorization code flow)."""

    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    API_URL = "https://api.github.com/user"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._settings = get_settings()
        self._client = client or httpx.AsyncClient(timeout=10)

    def is_configured(self) -> bool:
        return bool(self._settings.github_client_id and self._settings.github_client_secret)

    def authorization_url(self, state: str) -> str:
        redirect_uri = self._settings.github_redirect_uri
        params = {
            "client_id": self._settings.github_client_id,
            "redirect_uri": redirect_uri or "",
            # Sprint 3A: `repo` lets EvoShield list and import the user's
            # (private) repositories and refresh their metadata. Narrower
            # scopes would break private-repo listing for the import flow.
            "scope": "read:user user:email repo",
            "state": state,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> str:
        """Exchange an authorization code for an access token."""
        try:
            response = await self._client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self._settings.github_client_id,
                    "client_secret": self._settings.github_client_secret,
                    "code": code,
                    "redirect_uri": self._settings.github_redirect_uri or "",
                },
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise ProviderError("GitHub OAuth service unavailable") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("GitHub authorization returned an invalid response") from exc
        if "access_token" not in payload:
            raise ProviderError(payload.get("error_description") or "GitHub authorization failed")
        return str(payload["access_token"])

    async def fetch_user(self, access_token: str) -> AuthUser:
        try:
            response = await self._client.get(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        except httpx.HTTPError as exc:
            raise ProviderError("GitHub API unavailable") from exc
        if response.status_code >= 400:
            raise ProviderError("GitHub user lookup failed")
        data: dict[str, Any] = response.json()
        return AuthUser(
            id=str(data.get("id", "")),
            email=str(data.get("email") or f"{data.get('login')}@users.noreply.github.com"),
            full_name=data.get("name"),
            avatar_url=data.get("avatar_url"),
            provider="github",
            provider_sub=str(data.get("id", "")),
        )
