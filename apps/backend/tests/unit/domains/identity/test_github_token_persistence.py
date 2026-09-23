"""GitHub OAuth token persistence (Sprint 3A).

Proves the identity service's `github_callback` stores the exchanged access
token in `provider_tokens`, so the repository integration layer can later
call the GitHub API as the user without re-exchanging the code. The OAuth
client is faked — no network.
"""

import asyncio
import uuid

from sqlalchemy import select

from app.db.session import session_factory
from app.domains.identity.identifiers import resolve_user_id
from app.domains.identity.ports import AuthUser
from app.domains.identity.service import IdentityService
from app.models.provider_token import ProviderToken
from app.models.user import User
from app.repositories.provider_token import ProviderTokenRepository


class FakeGitHubOAuth:
    """Stands in for `GitHubOAuthClient` with canned responses."""

    async def exchange_code(self, code: str) -> str:
        assert code == "test-code"
        return "gho_test_access_token"

    async def fetch_user(self, access_token: str) -> AuthUser:
        assert access_token == "gho_test_access_token"
        return AuthUser(
            id="583231",
            email="octocat@users.noreply.github.com",
            full_name="The Octocat",
            avatar_url=None,
            provider="github",
            provider_sub="583231",
        )


class NoopAuthProvider:
    """The callback path never touches the AuthProvider port."""

    async def register(self, *args):  # pragma: no cover - not exercised
        raise NotImplementedError

    async def login(self, *args):  # pragma: no cover
        raise NotImplementedError

    async def verify_token(self, *args):  # pragma: no cover
        raise NotImplementedError

    async def logout(self, *args):  # pragma: no cover
        raise NotImplementedError


def test_github_callback_persists_access_token() -> None:
    async def scenario() -> None:
        service = IdentityService(
            provider=NoopAuthProvider(),  # type: ignore[arg-type]
            github=FakeGitHubOAuth(),  # type: ignore[arg-type]
        )
        result = await service.github_callback("test-code")
        assert result.access_token
        assert result.user.email == "octocat@users.noreply.github.com"

        user_id = resolve_user_id("github", "583231")

        async with session_factory() as session:
            token = await ProviderTokenRepository(session).get_access_token(user_id, "github")
            assert token == "gho_test_access_token"

            rows = (
                (
                    await session.execute(
                        select(ProviderToken).where(ProviderToken.user_id == user_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].provider == "github"
            # ADR 0018: write:public_key added for ephemeral deploy-key creation.
            assert rows[0].scope == "read:user user:email repo write:public_key"

    asyncio.run(scenario())


def test_token_upsert_is_idempotent() -> None:
    async def scenario() -> None:
        user_id = uuid.uuid4()
        # A real `users` row is required — provider_tokens.user_id is an FK
        # that Postgres enforces (SQLite does not unless pragmas are on).
        async with session_factory() as session:
            session.add(
                User(
                    id=user_id,
                    email=f"token-{uuid.uuid4().hex[:8]}@example.com",
                    auth_provider="github",
                )
            )
            await session.commit()

        async with session_factory() as session:
            repo = ProviderTokenRepository(session)
            await repo.upsert(
                user_id=user_id, provider="github", access_token="token-one", scope="repo"
            )
            await session.commit()

        async with session_factory() as session:
            repo = ProviderTokenRepository(session)
            await repo.upsert(
                user_id=user_id, provider="github", access_token="token-two", scope="repo"
            )
            await session.commit()

        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ProviderToken).where(ProviderToken.user_id == user_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].access_token == "token-two"

    asyncio.run(scenario())
