"""Identity domain data access — user profile persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.identity.identifiers import resolve_user_id
from app.domains.identity.ports import AuthUser
from app.models.user import User


class UserRepository:
    """Persists and reads application-side user profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: object) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert_from_auth(self, auth_user: AuthUser) -> User:
        """Create-or-update a profile row mirroring a provider identity.

        Resolves a stable application user id from the provider subject
        (see `identifiers.resolve_user_id`) so re-authentication never
        duplicates rows, then records the provider linkage on the profile.
        """
        user_id = resolve_user_id(auth_user.provider, auth_user.id)
        existing = await self.get_by_id(user_id)
        if existing is None:
            existing = await self.get_by_email(auth_user.email)
        if existing is None:
            existing = User(
                id=user_id,
                email=auth_user.email,
                full_name=auth_user.full_name,
                avatar_url=auth_user.avatar_url,
                auth_provider=auth_user.provider,
                auth_provider_sub=auth_user.provider_sub,
            )
            self._session.add(existing)
        else:
            existing.email = auth_user.email
            existing.full_name = auth_user.full_name or existing.full_name
            existing.avatar_url = auth_user.avatar_url or existing.avatar_url
            existing.auth_provider = auth_user.provider
            existing.auth_provider_sub = auth_user.provider_sub
        await self._session.flush()
        return existing
