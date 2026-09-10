"""Shared data access for provider tokens.

Two domains touch `provider_tokens`: the `identity` domain writes it during
the GitHub OAuth callback, and the `github` domain reads it to obtain the
user's GitHub access token. Per the layout rule in this package
("shared here when several domains read the same table"), the repository
lives in the shared data-access layer rather than inside either domain.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.identity.repository import UserRepository
from app.models.provider_token import ProviderToken


class ProviderTokenRepository:
    """Reads and writes per-user provider access tokens.

    Depends on `UserRepository` for the application-side user lookup used
    when storing a token before the profile row has been committed.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = UserRepository(session)

    async def get_access_token(self, user_id: uuid.UUID, provider: str = "github") -> str | None:
        """Return the stored token for (user, provider), or None if absent."""
        stmt = select(ProviderToken).where(
            ProviderToken.user_id == user_id,
            ProviderToken.provider == provider,
        )
        token = (await self._session.execute(stmt)).scalar_one_or_none()
        return token.access_token if token is not None else None

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        access_token: str,
        scope: str | None = None,
        expires_at: datetime | None = None,
    ) -> ProviderToken:
        """Create or replace the token for (user, provider)."""
        stmt = select(ProviderToken).where(
            ProviderToken.user_id == user_id,
            ProviderToken.provider == provider,
        )
        token = (await self._session.execute(stmt)).scalar_one_or_none()
        if token is None:
            token = ProviderToken(
                user_id=user_id,
                provider=provider,
                access_token=access_token,
                scope=scope,
                expires_at=expires_at,
            )
            self._session.add(token)
        else:
            token.access_token = access_token
            token.scope = scope or token.scope
            token.expires_at = expires_at or token.expires_at
        await self._session.flush()
        return token
