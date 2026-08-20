"""Tests for the Semgrep analysis provider.

Verifies the full provider lifecycle with mocked workspace, runner, and
findings callback.  No real Semgrep binary required.
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
from app.domains.scanners.providers.semgrep.provider import SemgrepProvider
from app.domains.scanners.providers.semgrep.runner import SemgrepResult

_FAKE_SOURCE = "VERY_SENSITIVE_TEST_SOURCE_CODE"
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


class TestSemgrepProviderRegistration:
    """Verify Semgrep is in the scanner registry."""

    def test_registered_in_registry(self) -> None:
        from app.domains.scanners.registry import get_registered_scanners

        scanners = get_registered_scanners()
        assert "semgrep" in scanners
        assert "trivy" in scanners
        assert "gitleaks" in scanners

    def test_build_from_registry(self) -> None:
        from app.core.config import Settings
        from app.domains.scanners.registry import build_scanner

        settings = Settings()
        provider = build_scanner("semgrep", settings)
        assert provider.name == "semgrep"

    def test_unknown_scanner_raises(self) -> None:
        from app.core.config import Settings
        from app.domains.scanners.registry import build_scanner

        settings = Settings()
        with pytest.raises(ProviderError, match="Unknown scanner"):
            build_scanner("nonexistent", settings)


class TestSemgrepProviderExecution:
    """Verify the full execution pipeline with mocked components."""

    @pytest.mark.asyncio
    async def test_successful_execution_persists_findings(self, tmp_path: Path) -> None:
        context = _make_context()
        findings_callback = AsyncMock()

        provider = SemgrepProvider(findings_callback=findings_callback)

        valid_output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "python.lang.security.audit.dangerous-subprocess-call",
                        "path": "app/utils.py",
                        "start": {"line": 42, "col": 5},
                        "extra": {
                            "message": "Dangerous subprocess call",
                            "severity": "ERROR",
                        },
                    }
                ]
            }
        )

        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.get_version",
                return_value="1.56.0",
            ),
            patch.object(
                provider._runner,
                "run_scan",
                return_value=SemgrepResult(exit_code=1, stdout=valid_output, stderr=""),
            ),
        ):
            await provider.execute(context)

        findings_callback.assert_called_once()
        persisted_findings = findings_callback.call_args[0][0]
        assert len(persisted_findings) == 1
        assert persisted_findings[0].finding_type == FindingType.SAST

    @pytest.mark.asyncio
    async def test_no_findings_on_empty_output(self, tmp_path: Path) -> None:
        context = _make_context()
        findings_callback = AsyncMock()

        provider = SemgrepProvider(findings_callback=findings_callback)
        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.get_version",
                return_value="1.56.0",
            ),
            patch.object(
                provider._runner,
                "run_scan",
                return_value=SemgrepResult(exit_code=0, stdout='{"results": []}', stderr=""),
            ),
        ):
            await provider.execute(context)

        findings_callback.assert_called_once_with([])

    @pytest.mark.asyncio
    async def test_scanner_unavailable_raises(self) -> None:
        context = _make_context()
        provider = SemgrepProvider()

        with patch(
            "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.is_available",
            return_value=False,
        ):
            with pytest.raises(ProviderError) as exc_info:
                await provider.execute(context)
            assert exc_info.value.code == "scanner_unavailable"

    @pytest.mark.asyncio
    async def test_cancellation_before_execution(self) -> None:
        context = _make_context()
        context.cancel_event.set()
        provider = SemgrepProvider()

        with pytest.raises(AnalysisCancelledError):
            await provider.execute(context)

    @pytest.mark.asyncio
    async def test_cancellation_after_acquisition(self, tmp_path: Path) -> None:
        context = _make_context()
        provider = SemgrepProvider()

        async def _fake_acquire(ctx):
            context.cancel_event.set()
            return _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", side_effect=_fake_acquire),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.get_version",
                return_value="1.56.0",
            ),
        ):
            with pytest.raises(AnalysisCancelledError):
                await provider.execute(context)

    @pytest.mark.asyncio
    async def test_workspace_cleanup_on_success(self, tmp_path: Path) -> None:
        context = _make_context()
        provider = SemgrepProvider(findings_callback=AsyncMock())
        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.get_version",
                return_value="1.56.0",
            ),
            patch.object(
                provider._runner,
                "run_scan",
                return_value=SemgrepResult(exit_code=0, stdout='{"results":[]}', stderr=""),
            ),
        ):
            await provider.execute(context)

        mock_workspace.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_workspace_cleanup_on_failure(self, tmp_path: Path) -> None:
        context = _make_context()
        provider = SemgrepProvider()
        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.get_version",
                return_value="1.56.0",
            ),
            patch.object(
                provider._runner,
                "run_scan",
                return_value=SemgrepResult(exit_code=99, stdout="", stderr="error"),
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
        provider = SemgrepProvider()
        mock_workspace = _mock_workspace(tmp_path)

        with (
            patch.object(provider, "_acquire_repository", return_value=mock_workspace),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.is_available",
                return_value=True,
            ),
            patch(
                "app.domains.scanners.providers.semgrep.runner.SemgrepRunner.get_version",
                return_value="1.56.0",
            ),
            patch.object(
                provider._runner,
                "run_scan",
                return_value=SemgrepResult(
                    exit_code=99, stdout="", stderr=f"error with {_FAKE_SOURCE}"
                ),
            ),
        ):
            with pytest.raises(ProviderError) as exc_info:
                await provider.execute(context)

        # The fake source must NOT appear in the ProviderError message
        assert _FAKE_SOURCE not in str(exc_info.value)

    def test_supports_non_archived_repo(self) -> None:
        provider = SemgrepProvider()
        repo = MagicMock(archived=False, disabled=False)
        assert provider.supports(repo) is True

    def test_rejects_archived_repo(self) -> None:
        provider = SemgrepProvider()
        repo = MagicMock(archived=True, disabled=False)
        assert provider.supports(repo) is False

    def test_rejects_disabled_repo(self) -> None:
        provider = SemgrepProvider()
        repo = MagicMock(archived=False, disabled=True)
        assert provider.supports(repo) is False
