"""Shared FastAPI dependencies (dependency-injection plumbing)."""

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.db.session import session_factory
from app.domains.analysis.orchestrator import AnalysisOrchestrator
from app.domains.analysis.ports import AnalysisProvider
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


def _trivy_token_factory(owner_id: uuid.UUID) -> Callable[[], Awaitable[str | None]]:
    """Create an async callable that resolves the GitHub token for *owner_id*."""

    async def _resolve() -> str | None:
        async with session_factory() as s:
            token_repo = ProviderTokenRepository(s)
            return await token_repo.get_access_token(owner_id, "github")

    return _resolve


def get_analysis_orchestrator(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisOrchestrator:
    """Provide a request-scoped analysis orchestrator.

    Multi-scanner mode (Sprint 5C.1): when ANALYSIS_SCANNERS is set,
    builds a list of providers and passes them as scanner_providers.
    Single-provider mode (backward compatible): uses ANALYSIS_PROVIDER.
    """
    settings = get_settings()

    # Multi-scanner mode: ANALYSIS_SCANNERS takes precedence.
    if settings.analysis_scanners:
        from app.domains.scanners.registry import build_scanner, parse_scanner_list

        scanner_names = parse_scanner_list(settings.analysis_scanners)
        providers = [build_scanner(name, settings) for name in scanner_names]
        providers = [_wrap_provider_with_findings(p, settings) for p in providers]
        return AnalysisOrchestrator(
            session=session,
            session_factory=session_factory,
            scanner_providers=providers,
            queued_hold_seconds=settings.analysis_queued_hold_seconds,
            timeout_seconds=settings.analysis_run_timeout_seconds,
            scanner_timeout_seconds=settings.scanner_timeout_seconds,
            token_resolver_factory=_trivy_token_factory,
        )

    # Single-provider mode (backward compatible).
    provider = _build_provider_with_findings(settings)
    return AnalysisOrchestrator(
        session=session,
        session_factory=session_factory,
        provider=provider,
        queued_hold_seconds=settings.analysis_queued_hold_seconds,
        timeout_seconds=settings.analysis_run_timeout_seconds,
        token_resolver_factory=_trivy_token_factory,
    )


def _build_provider_with_findings(settings: Settings):
    """Build the analysis provider with a findings persistence callback.

    When a real scanner (Trivy) completes a scan, it produces findings that
    need to be persisted to the database.  The callback creates a fresh
    session from the factory and writes findings through the repository.
    """
    from app.domains.scanners.repository import FindingRepository

    if settings.analysis_provider == "fake":
        from app.domains.analysis.providers.fake import FakeAnalysisProvider

        return FakeAnalysisProvider(
            delay_seconds=settings.analysis_fake_delay_seconds,
            fail=settings.analysis_fake_fail,
        )

    if settings.analysis_provider == "trivy":
        from app.domains.scanners.providers.trivy.provider import TrivyProvider

        async def _persist_findings(findings):
            async with session_factory() as s:
                repo = FindingRepository(s)
                await repo.create_many(findings)
                await s.commit()

        return TrivyProvider(
            executable=settings.trivy_executable,
            timeout_seconds=settings.trivy_timeout_seconds,
            findings_callback=_persist_findings,
        )

    from app.core.exceptions import ProviderError

    raise ProviderError(
        f"Unknown analysis provider: {settings.analysis_provider!r}. Available: fake, trivy."
    )


def _wrap_provider_with_findings(
    provider: AnalysisProvider, settings: Settings
) -> AnalysisProvider:
    """Wrap a real scanner provider with a findings persistence callback.

    For the Trivy provider, this injects a callback that persists findings.
    For other providers (future: gitleaks, semgrep), the same pattern applies.
    """
    from app.domains.scanners.repository import FindingRepository

    if not hasattr(provider, "_findings_callback"):
        # Provider does not support findings callback (e.g., fake provider).
        return provider

    async def _persist_findings(findings):
        async with session_factory() as s:
            repo = FindingRepository(s)
            await repo.create_many(findings)
            await s.commit()

    provider._findings_callback = _persist_findings  # type: ignore[attr-defined]
    return provider


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
