"""Local auth provider — the zero-dependency dev fallback.

Implements the `AuthProvider` port with credentials stored in
`auth_credentials` (Argon2id hashes) and HS256 access tokens signed with the
configured session secret. Used automatically when Supabase credentials are
not configured, mirroring the SQLite database fallback decision
(ADR 0001). Never enabled in production.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.db.session import session_factory
from app.domains.identity.jwt import create_access_token, decode_access_token
from app.domains.identity.passwords import hash_password, verify_password
from app.domains.identity.ports import AuthResult, AuthUser, TokenClaims
from app.models.credential import AuthCredential
from app.models.user import User


class LocalAuthProvider:
    """Email/password auth with Argon2id hashing and HS256 tokens."""

    async def register(self, email: str, password: str, full_name: str | None) -> AuthResult:
        async with session_factory() as session:
            existing = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if existing is not None:
                raise ConflictError("An account with this email already exists")

            user_id = uuid.uuid4()
            session.add(AuthCredential(user_id=user_id, password_hash=hash_password(password)))
            session.add(
                User(
                    id=user_id,
                    email=email,
                    full_name=full_name,
                    auth_provider="local",
                    auth_provider_sub=str(user_id),
                )
            )
            await session.commit()

        return self._issue_result(user_id, email, full_name, provider_sub=str(user_id))

    async def login(self, email: str, password: str) -> AuthResult:
        async with session_factory() as session:
            user = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is None:
                raise UnauthorizedError("Invalid email or password")
            credential = (
                await session.execute(
                    select(AuthCredential).where(AuthCredential.user_id == user.id)
                )
            ).scalar_one_or_none()
            if credential is None or not verify_password(password, credential.password_hash):
                raise UnauthorizedError("Invalid email or password")
            user.last_login_at = datetime.now(UTC)
            await session.commit()
            return self._issue_result(
                user.id, user.email, user.full_name, provider_sub=user.auth_provider_sub
            )

    async def verify_token(self, token: str) -> TokenClaims:
        try:
            return decode_access_token(token)
        except Exception as exc:
            raise UnauthorizedError("Invalid or expired token") from exc

    async def logout(self, token: str) -> None:
        # Stateless HS256 tokens: nothing to revoke server-side. The client
        # clears the session cookie; token expiry bounds the lifetime.
        return None

    def _issue_result(
        self, user_id: uuid.UUID, email: str, full_name: str | None, *, provider_sub: str | None
    ) -> AuthResult:
        settings = get_settings()
        token = create_access_token(sub=str(user_id), email=email, provider="local")
        return AuthResult(
            access_token=token,
            token_type="bearer",
            expires_in=settings.session_max_age_seconds,
            user=AuthUser(
                id=str(user_id),
                email=email,
                full_name=full_name,
                avatar_url=None,
                provider="local",
                provider_sub=provider_sub or str(user_id),
            ),
        )
