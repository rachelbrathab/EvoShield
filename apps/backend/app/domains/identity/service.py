"""Identity domain business logic.

`IdentityService` orchestrates the `AuthProvider` port and profile
provisioning. It owns the application-side rules: an authenticated identity
always has a `users` profile row, GitHub logins map to a provider identity,
and session cookies are derived from the provider's access token.
"""

import logging
import uuid

from app.core.config import get_settings
from app.core.exceptions import ProviderError, UnauthorizedError
from app.db.session import session_factory
from app.domains.identity.github_oauth import GitHubOAuthClient
from app.domains.identity.identifiers import resolve_user_id
from app.domains.identity.jwt import create_access_token
from app.domains.identity.ports import AuthProvider, AuthResult, AuthUser, TokenClaims
from app.domains.identity.repository import UserRepository
from app.models.user import User

logger = logging.getLogger(__name__)


class IdentityService:
    """Facade over authentication + profile provisioning."""

    def __init__(self, provider: AuthProvider, github: GitHubOAuthClient) -> None:
        self._provider = provider
        self._github = github

    async def register(self, email: str, password: str, full_name: str | None) -> AuthResult:
        result = await self._provider.register(email, password, full_name)
        await self._sync_profile(result.user)
        return result

    async def login(self, email: str, password: str) -> AuthResult:
        result = await self._provider.login(email, password)
        await self._sync_profile(result.user)
        return result

    async def github_authorization_url(self) -> tuple[str, str]:
        """Return (authorize_url, state). The caller stores `state` (CSRF)."""
        if not self._github.is_configured():
            raise ProviderError("GitHub OAuth is not configured")
        state = uuid.uuid4().hex
        return self._github.authorization_url(state), state

    async def github_callback(self, code: str) -> AuthResult:
        access_token = await self._github.exchange_code(code)
        auth_user = await self._github.fetch_user(access_token)
        await self._sync_profile(auth_user)

        settings = get_settings()
        token = create_access_token(sub=auth_user.id, email=auth_user.email, provider="github")
        return AuthResult(
            access_token=token,
            token_type="bearer",
            expires_in=settings.session_max_age_seconds,
            user=auth_user,
        )

    async def authenticate(self, token: str) -> User:
        """Verify a token and return the application user profile."""
        claims = await self._provider.verify_token(token)
        profile = await self._load_or_create_profile(claims)
        if profile is None:
            raise UnauthorizedError("Unknown user identity")
        return profile

    async def logout(self, token: str) -> None:
        await self._provider.logout(token)

    async def _sync_profile(self, auth_user: AuthUser) -> None:
        """Ensure a profile row exists for an authenticated identity."""
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.upsert_from_auth(auth_user)
            await session.commit()

    async def _load_or_create_profile(self, claims: TokenClaims) -> User | None:
        async with session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_id(resolve_user_id(claims.provider, claims.sub))
            if user is None:
                # Identity exists in the provider but not as a profile yet —
                # provision it lazily (e.g. token minted before profile sync).
                user = await repo.upsert_from_auth(
                    AuthUser(
                        id=claims.sub,
                        email=claims.email,
                        full_name=None,
                        avatar_url=None,
                        provider=claims.provider,
                        provider_sub=claims.sub,
                    )
                )
                await session.commit()
            return user
