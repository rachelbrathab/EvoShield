"""Shared FastAPI dependencies (dependency-injection plumbing)."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.db.session import session_factory
from app.domains.analysis.factory import build_analysis_provider
from app.domains.analysis.orchestrator import AnalysisOrchestrator
from app.domains.github.service import RepositoryService
from app.domains.identity.service import IdentityService
from app.models.user import User
from app.repositories.provider_token import ProviderTokenRepository

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a request-scoped database session.

    The session is opened and closed per request; repositories receive it
    through this dependency rather than importing it directly (Dependency
    Inversion — see docs/architecture.md).
    """
    async with session_factory() as session:
        yield session


def get_app_settings() -> Settings:
    """Provide the settings singleton to routes/services."""
    return get_settings()


def get_identity_service() -> IdentityService:
    """Provide the identity domain service (cached provider selection)."""
    from app.domains.identity.factory import build_identity_service

    return build_identity_service()


def get_repository_service(session: Annotated[AsyncSession, Depends(get_db)]) -> RepositoryService:
    """Provide a request-scoped repository integration service.

    The service receives the request session and the shared token store;
    the GitHub client is created per operation, bound to the authenticated
    user's access token (see `RepositoryService._client_for`).
    """
    return RepositoryService(
        session=session,
        token_provider=ProviderTokenRepository(session),
    )


def get_analysis_orchestrator(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisOrchestrator:
    """Provide a request-scoped analysis orchestrator.

    The orchestrator receives the request session for synchronous work plus a
    session factory for the background execution task (which outlives the
    request). The provider comes from settings via the domain factory — the
    fake today, real scanners later.
    """
    settings = get_settings()
    return AnalysisOrchestrator(
        session=session,
        session_factory=session_factory,
        provider=build_analysis_provider(settings),
        queued_hold_seconds=settings.analysis_queued_hold_seconds,
        timeout_seconds=settings.analysis_run_timeout_seconds,
    )


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    """Resolve the access token from the Authorization header or session cookie."""
    if credentials is not None:
        return credentials.credentials
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise UnauthorizedError("Not authenticated")
    return token


async def get_current_user(
    request: Request,
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> User:
    """Resolve the authenticated user for a request (protected-route guard)."""
    token = _extract_token(request, credentials)
    return await identity.authenticate(token)
