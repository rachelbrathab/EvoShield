"""Supabase auth provider — production authentication.

Talks to the Supabase Auth REST API (GoTrue) and verifies the JWTs Supabase
issues. Used when `SUPABASE_URL`/`SUPABASE_JWT_SECRET` are configured;
otherwise the `LocalAuthProvider` is the dev fallback (see `factory.py`).
"""

from datetime import UTC, datetime

import httpx
import jwt

from app.core.config import get_settings
from app.core.exceptions import ProviderError, UnauthorizedError
from app.domains.identity.ports import AuthResult, AuthUser, TokenClaims


class SupabaseAuthProvider:
    """Email/password auth against Supabase Auth (GoTrue REST API)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._settings = get_settings()
        self._client = client or httpx.AsyncClient(timeout=10)

    async def register(self, email: str, password: str, full_name: str | None) -> AuthResult:
        url = f"{self._settings.supabase_url}/auth/v1/signup"
        body: dict[str, object] = {"email": email, "password": password}
        if full_name:
            body["data"] = {"full_name": full_name}
        data = await self._post(url, body)
        if data.get("access_token"):
            return self._auth_result_from_session(data)
        # Email confirmation may be required; attempt a sign-in to obtain a session.
        return await self.login(email, password)

    async def login(self, email: str, password: str) -> AuthResult:
        url = f"{self._settings.supabase_url}/auth/v1/token?grant_type=password"
        data = await self._post(url, {"email": email, "password": password})
        return self._auth_result_from_session(data)

    async def verify_token(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"require": ["sub", "exp"]},
            )
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid or expired token") from exc
        return TokenClaims(
            sub=str(payload["sub"]),
            email=str(payload.get("email", "")),
            provider="supabase",
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )

    async def logout(self, token: str) -> None:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            await self._client.post(
                f"{self._settings.supabase_url}/auth/v1/logout",
                headers=self._anon_headers(headers),
            )
        except httpx.HTTPError:  # logout must never break the flow
            return None

    async def _post(self, url: str, body: dict) -> dict:
        try:
            response = await self._client.post(url, json=body, headers=self._anon_headers())
        except httpx.HTTPError as exc:
            raise ProviderError("Authentication service unavailable") from exc
        if response.status_code >= 400:
            detail = self._error_detail(response)
            raise ProviderError(detail)
        return response.json()

    def _anon_headers(self, extra: dict | None = None) -> dict:
        headers = {
            "apikey": self._settings.supabase_anon_key or "",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "Authentication failed"
        detail = payload.get("error_description") or payload.get("msg") or payload.get("message")
        return str(detail) if detail else "Authentication failed"

    def _auth_result_from_session(self, data: dict) -> AuthResult:
        user = data.get("user", {})
        expires_in = int(data.get("expires_in", 3600))
        return AuthResult(
            access_token=str(data["access_token"]),
            token_type=str(data.get("token_type", "bearer")),
            expires_in=expires_in,
            user=AuthUser(
                id=str(user.get("id", "")),
                email=str(user.get("email", "")),
                full_name=(user.get("user_metadata") or {}).get("full_name"),
                avatar_url=(user.get("user_metadata") or {}).get("avatar_url"),
                provider="supabase",
                provider_sub=str(user.get("id", "")),
            ),
        )
