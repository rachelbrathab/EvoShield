"""Tests for the Grype analysis provider.

Verifies the full provider lifecycle with mocked workspace, runner, and
findings callback.  No real Syft/Grype binaries required.
"""

import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ProviderError
from app.domains.analysis.ports import AnalysisCancelledError, AnalysisExecutionContext
from app.domains.scanners.enums import FindingType
from app.domains.scanners.providers.grype.provider import GrypeProvider
from app.domains.scanners.providers.grype.runner import GrypeResult

_FAKE_SBOM = "VERY_SENSITIVE_TEST_SBOM_CONTENT"
_RUN_ID = uuid.uuid4()
_OWNER_ID = uuid.uuid4()
_REPO_ID = uuid.uuid4()


def _make_context(**overrides) -> AnalysisExecutionContext:
    """Build a minimal AnalysisExecutionContext for testing."""
    defaults = {
        "run_id": _RUN_ID,
        "repository_id": _REPO_ID,
        "full_name": "test-owner/test-repo",
        "cancel_event": asyncio.Event(),
        "owner_id": _OWNER_ID,
        "token_resolver": AsyncMock(return_value="ghp_fake_token"),
    }
    defaults.update(overrides)
    return AnalysisExecutionContext(**defaults)


def _mock_workspace(tmp_path: Path) -> MagicMock:
    """Create a mock WorkspaceHandle."""
    ws = MagicMock()
    ws.repo_path = tmp_path
    ws.cleanup.return_value = None
    return ws


class TestGrypeProviderRegistration:
    """Verify Grype is in the scanner registry."""

    def test_registered_in_registry(self) -> None:
        from app.domains.scanners.registry import get_registered_scanners

        scanners = get_registered_scanners()
        assert "grype" in scanners
        assert "trivy" in scanners
        assert "gitleaks" in scanners
        assert "semgrep" in scanners

    def test_build_from_registry(self) -> None:
        from app.core.config import Settings
        from app.domains.scanners.registry import build_scanner

        settings = Settings()
        provider = build_scanner("grype", settings)
        assert provider.name == "grype"

    def test_unknown_scanner_raises(self) -> None:
        from app.core.config import Settings
        from app.domains.scanners.registry import build_scanner

        settings = Settings()
        with pytest.raises(ProviderError, match="Unknown scanner"):
            build_scanner("nonexistent", settings)


class TestGrypeProviderExecution:
    """Verify the full execution pipeline with mocked components."""

    @pytest.mark.asyncio
    async def test_successful_execution_persists_findings(self, tmp_path: Path) -> None:
        context = _make_context()
        findings_callback = AsyncMock()
        provider = GrypeProvider(findings_callback=findings_callback)

        valid_output = json.dumps(
            {
                "matches": [
                    {
                        "vulnerability": {
                            "id": "CVE-2024-1234",
                            "severity": "High",
                            "description": "Test vuln",
                        },
                        "artifact": {
                            "name": "requests",
                            "version": "2.28.0",
                            "type": "python",
                        },
                    }
                ]
            }
        )

        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.get_version",
                return_value="0.1.0",
            ),
            patch.object(
                provider._runner,
                "run_pipeline",
                return_value=GrypeResult(exit_code=0, stdout=valid_output, stderr=""),
            ),
        ):
            await provider.execute(context)

        findings_callback.assert_called_once()
        persisted_findings = findings_callback.call_args[0][0]
        assert len(persisted_findings) == 1
        assert persisted_findings[0].finding_type == FindingType.VULNERABILITY

    @pytest.mark.asyncio
    async def test_no_findings_on_empty_output(self, tmp_path: Path) -> None:
        context = _make_context()
        findings_callback = AsyncMock()
        provider = GrypeProvider(findings_callback=findings_callback)
        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.get_version",
                return_value="0.1.0",
            ),
            patch.object(
                provider._runner,
                "run_pipeline",
                return_value=GrypeResult(exit_code=0, stdout='{"matches":[]}', stderr=""),
            ),
        ):
            await provider.execute(context)

        findings_callback.assert_called_once_with([])

    @pytest.mark.asyncio
    async def test_syft_unavailable_raises(self) -> None:
        context = _make_context()
        provider = GrypeProvider()

        def _available(name):
            if name == "syft":
                return False
            return True

        with patch(
            "app.domains.scanners.providers.grype.runner.GrypeRunner.is_available",
            side_effect=_available,
        ):
            with pytest.raises(ProviderError) as exc_info:
                await provider.execute(context)
            assert exc_info.value.code == "scanner_unavailable"

    @pytest.mark.asyncio
    async def test_grype_unavailable_raises(self) -> None:
        context = _make_context()
        provider = GrypeProvider()

        def _available(name):
            if name == "grype":
                return False
            return True

        with patch(
            "app.domains.scanners.providers.grype.runner.GrypeRunner.is_available",
            side_effect=_available,
        ):
            with pytest.raises(ProviderError) as exc_info:
                await provider.execute(context)
            assert exc_info.value.code == "scanner_unavailable"

    @pytest.mark.asyncio
    async def test_cancellation_before_execution(self) -> None:
        context = _make_context()
        context.cancel_event.set()
        provider = GrypeProvider()

        with pytest.raises(AnalysisCancelledError):
            await provider.execute(context)

    @pytest.mark.asyncio
    async def test_cancellation_after_acquisition(self, tmp_path: Path) -> None:
        context = _make_context()
        provider = GrypeProvider()

        async def _fake_acquire(ctx):
            context.cancel_event.set()
            return _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", side_effect=_fake_acquire),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.get_version",
                return_value="0.1.0",
            ),
        ):
            with pytest.raises(AnalysisCancelledError):
                await provider.execute(context)

    @pytest.mark.asyncio
    async def test_workspace_cleanup_on_success(self, tmp_path: Path) -> None:
        context = _make_context()
        provider = GrypeProvider(findings_callback=AsyncMock())
        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.get_version",
                return_value="0.1.0",
            ),
            patch.object(
                provider._runner,
                "run_pipeline",
                return_value=GrypeResult(exit_code=0, stdout='{"matches":[]}', stderr=""),
            ),
        ):
            await provider.execute(context)

        mock_workspace.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_workspace_cleanup_on_failure(self, tmp_path: Path) -> None:
        context = _make_context()
        provider = GrypeProvider()
        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.get_version",
                return_value="0.1.0",
            ),
            patch.object(
                provider._runner,
                "run_pipeline",
                return_value=GrypeResult(exit_code=99, stdout="", stderr="error"),
            ),
        ):
            with pytest.raises(ProviderError) as exc_info:
                await provider.execute(context)
            assert exc_info.value.code == "scanner_execution_failed"

        mock_workspace.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stderr_not_in_error_message(self, tmp_path: Path) -> None:
        """Even error messages must not leak scanner output."""
        context = _make_context()
        provider = GrypeProvider()
        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.grype.runner.GrypeRunner.get_version",
                return_value="0.1.0",
            ),
            patch.object(
                provider._runner,
                "run_pipeline",
                return_value=GrypeResult(
                    exit_code=99, stdout="", stderr=f"error with {_FAKE_SBOM}"
                ),
            ),
        ):
            with pytest.raises(ProviderError) as exc_info:
                await provider.execute(context)

        # The fake content must NOT appear in the ProviderError message
        assert _FAKE_SBOM not in str(exc_info.value)

    def test_supports_non_archived_repo(self) -> None:
        provider = GrypeProvider()
        repo = MagicMock(archived=False, disabled=False)
        assert provider.supports(repo) is True

    def test_rejects_archived_repo(self) -> None:
        provider = GrypeProvider()
        repo = MagicMock(archived=True, disabled=False)
        assert provider.supports(repo) is False

    def test_rejects_disabled_repo(self) -> None:
        provider = GrypeProvider()
        repo = MagicMock(archived=False, disabled=True)
        assert provider.supports(repo) is False
