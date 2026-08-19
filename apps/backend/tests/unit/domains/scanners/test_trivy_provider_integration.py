"""Integration tests for TrivyProvider with GitHubRepositorySource.

Tests the complete pipeline: GitHub acquisition -> Trivy scan -> parse -> persist.
All subprocess and GitHub calls are mocked.
"""

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ProviderError
from app.domains.analysis.ports import AnalysisCancelledError, AnalysisExecutionContext
from app.domains.scanners.providers.trivy.provider import TrivyProvider
from app.domains.scanners.providers.trivy.runner import TrivyResult


def _make_context(
    *,
    owner_id: uuid.UUID | None = None,
    full_name: str = "octocat/Hello-World",
    cancel_event: asyncio.Event | None = None,
) -> AnalysisExecutionContext:
    """Create a test execution context."""

    async def _token() -> str | None:
        return "ghp_test_token"

    return AnalysisExecutionContext(
        run_id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        full_name=full_name,
        cancel_event=cancel_event or asyncio.Event(),
        owner_id=owner_id or uuid.uuid4(),
        token_resolver=_token,
    )


def _mock_workspace() -> MagicMock:
    """Return a mock workspace with a real temp dir."""
    ws = MagicMock()
    ws.repo_path = Path("/tmp/test_repo")
    ws.cleanup = MagicMock()
    return ws


_TRIVY_AVAILABLE = patch("shutil.which", return_value="/usr/bin/trivy")


class TestTrivyProviderCancellation:
    """Verify cancellation is checked at multiple points."""

    @pytest.mark.asyncio
    async def test_cancelled_before_execution(self) -> None:
        provider = TrivyProvider()
        ctx = _make_context()
        ctx.cancel_event.set()

        with pytest.raises(AnalysisCancelledError):
            await provider.execute(ctx)

    @pytest.mark.asyncio
    async def test_cancelled_during_acquisition(self) -> None:
        provider = TrivyProvider()
        ctx = _make_context()

        async def _slow_acquire(*args: object, **kwargs: object) -> MagicMock:
            ctx.cancel_event.set()
            raise AnalysisCancelledError("cancelled")

        provider._acquire_repository = _slow_acquire  # type: ignore[method-assign]

        with _TRIVY_AVAILABLE:
            with pytest.raises(AnalysisCancelledError):
                await provider.execute(ctx)


class TestTrivyProviderErrorHandling:
    """Verify proper error codes for various failure modes."""

    @pytest.mark.asyncio
    async def test_scanner_unavailable(self) -> None:
        provider = TrivyProvider(executable="nonexistent_trivy")
        ctx = _make_context()

        with pytest.raises(ProviderError) as exc_info:
            await provider.execute(ctx)
        assert exc_info.value.code == "scanner_unavailable"

    @pytest.mark.asyncio
    async def test_github_not_connected(self) -> None:
        provider = TrivyProvider()

        async def _no_token() -> str | None:
            return None

        ctx = _make_context()
        ctx = AnalysisExecutionContext(
            run_id=ctx.run_id,
            repository_id=ctx.repository_id,
            full_name=ctx.full_name,
            cancel_event=ctx.cancel_event,
            owner_id=ctx.owner_id,
            token_resolver=_no_token,
        )

        with _TRIVY_AVAILABLE:
            with pytest.raises(ProviderError) as exc_info:
                await provider.execute(ctx)
            assert exc_info.value.code == "github_not_connected"


class TestTrivyProviderWorkspaceCleanup:
    """Verify workspace is always cleaned up after execution."""

    @pytest.mark.asyncio
    async def test_workspace_cleaned_on_success(self) -> None:
        provider = TrivyProvider()
        ctx = _make_context()
        ws = _mock_workspace()

        async def _mock_acquire(context: object) -> MagicMock:
            return ws

        provider._acquire_repository = _mock_acquire  # type: ignore[method-assign]

        with _TRIVY_AVAILABLE:
            with patch.object(
                provider._runner,
                "run_filesystem",
                new_callable=AsyncMock,
                return_value=TrivyResult(exit_code=0, stdout='{"Results": []}', stderr=""),
            ):
                await provider.execute(ctx)
                ws.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_workspace_cleaned_on_failure(self) -> None:
        provider = TrivyProvider()
        ctx = _make_context()
        ws = _mock_workspace()

        async def _mock_acquire(context: object) -> MagicMock:
            return ws

        provider._acquire_repository = _mock_acquire  # type: ignore[method-assign]

        with _TRIVY_AVAILABLE:
            with patch.object(
                provider._runner,
                "run_filesystem",
                new_callable=AsyncMock,
                side_effect=RuntimeError("scan crashed"),
            ):
                with pytest.raises(RuntimeError):
                    await provider.execute(ctx)
                ws.cleanup.assert_called_once()


class TestTrivyProviderFindingsPersistence:
    """Verify findings callback is invoked correctly."""

    @pytest.mark.asyncio
    async def test_empty_results_callback(self) -> None:
        callback = AsyncMock()
        provider = TrivyProvider(findings_callback=callback)
        ctx = _make_context()
        ws = _mock_workspace()

        async def _mock_acquire(context: object) -> MagicMock:
            return ws

        provider._acquire_repository = _mock_acquire  # type: ignore[method-assign]

        with _TRIVY_AVAILABLE:
            with patch.object(
                provider._runner,
                "run_filesystem",
                new_callable=AsyncMock,
                return_value=TrivyResult(exit_code=5, stdout="", stderr="no targets"),
            ):
                await provider.execute(ctx)
                callback.assert_called_once_with([])

    @pytest.mark.asyncio
    async def test_findings_callback_with_vulns(self) -> None:
        callback = AsyncMock()
        provider = TrivyProvider(findings_callback=callback)
        ctx = _make_context()
        ws = _mock_workspace()

        async def _mock_acquire(context: object) -> MagicMock:
            return ws

        provider._acquire_repository = _mock_acquire  # type: ignore[method-assign]

        trivy_output = (
            '{"Results":[{"Target":"requirements.txt","Class":"lang-pkgs",'
            '"Vulnerabilities":[{"VulnerabilityID":"CVE-2024-0001",'
            '"Severity":"HIGH","Title":"Test Vuln","PkgName":"flask",'
            '"InstalledVersion":"1.0","FixedVersion":"2.0",'
            '"PrimaryURL":"https://nvd.nist.gov/vuln/detail/CVE-2024-0001"}]}]}'
        )

        with _TRIVY_AVAILABLE:
            with patch.object(
                provider._runner,
                "run_filesystem",
                new_callable=AsyncMock,
                return_value=TrivyResult(exit_code=1, stdout=trivy_output, stderr=""),
            ):
                await provider.execute(ctx)
                callback.assert_called_once()
                findings = callback.call_args[0][0]
                assert len(findings) == 1
                assert findings[0].vulnerability_id == "CVE-2024-0001"
                assert findings[0].severity.value == "high"
                assert findings[0].package_name == "flask"
