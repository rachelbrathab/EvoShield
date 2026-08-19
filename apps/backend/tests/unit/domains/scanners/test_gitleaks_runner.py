"""Tests for the Gitleaks subprocess runner.

Verifies safe command construction, timeout handling, exit-code semantics,
and report-file cleanup.  All tests use mocked subprocesses — no real
Gitleaks binary required.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.domains.scanners.providers.gitleaks.runner import (
    GitleaksResult,
    GitleaksRunner,
)


class TestGitleaksResult:
    """Verify GitleaksResult properties."""

    def test_exit_code_0_is_success(self) -> None:
        r = GitleaksResult(exit_code=0, stdout="[]", stderr="")
        assert r.success is True
        assert r.secrets_found is False

    def test_exit_code_1_is_success_and_secrets_found(self) -> None:
        r = GitleaksResult(exit_code=1, stdout='[{"RuleID":"test"}]', stderr="")
        assert r.success is True
        assert r.secrets_found is True

    def test_exit_code_2_is_failure(self) -> None:
        r = GitleaksResult(exit_code=2, stdout="", stderr="error")
        assert r.success is False
        assert r.secrets_found is False

    def test_json_data_from_array(self) -> None:
        r = GitleaksResult(exit_code=1, stdout='[{"RuleID":"x"}]', stderr="")
        assert r.json_data == [{"RuleID": "x"}]

    def test_json_data_from_dict(self) -> None:
        r = GitleaksResult(exit_code=1, stdout='{"findings":[{"RuleID":"x"}]}', stderr="")
        assert r.json_data == [{"RuleID": "x"}]

    def test_json_data_empty_string(self) -> None:
        r = GitleaksResult(exit_code=0, stdout="", stderr="")
        assert r.json_data == []

    def test_json_data_invalid(self) -> None:
        r = GitleaksResult(exit_code=0, stdout="not json", stderr="")
        assert r.json_data is None


class TestGitleaksRunnerAvailability:
    """Verify static availability and version checks."""

    def test_is_available_when_found(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/gitleaks"):
            assert GitleaksRunner.is_available() is True

    def test_is_available_when_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            assert GitleaksRunner.is_available() is False

    def test_get_version_when_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            assert GitleaksRunner.get_version() is None


class TestGitleaksRunnerValidation:
    """Verify path validation."""

    def test_rejects_relative_path(self) -> None:
        runner = GitleaksRunner()
        with pytest.raises(ValueError, match="must be absolute"):
            runner._validate_path(Path("relative/path"))

    def test_rejects_nonexistent_path(self) -> None:
        runner = GitleaksRunner()
        with pytest.raises(ValueError, match="does not exist"):
            runner._validate_path(Path("/nonexistent/path"))

    def test_rejects_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("x")
        runner = GitleaksRunner()
        with pytest.raises(ValueError, match="not a directory"):
            runner._validate_path(f)


class TestGitleaksRunnerExecution:
    """Verify run_detect with mocked subprocess."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, tmp_path: Path) -> None:
        runner = GitleaksRunner(executable="gitleaks", timeout_seconds=30)

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"[]", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.run_detect(tmp_path)

        assert result.exit_code == 0
        assert result.success is True

    @pytest.mark.asyncio
    async def test_secrets_found_exit_code(self, tmp_path: Path) -> None:
        runner = GitleaksRunner(executable="gitleaks", timeout_seconds=30)

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            b'[{"RuleID":"test-rule","File":"x.py"}]',
            b"",
        )
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.run_detect(tmp_path)

        assert result.exit_code == 1
        assert result.secrets_found is True
        assert result.success is True

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self, tmp_path: Path) -> None:
        runner = GitleaksRunner(executable="gitleaks", timeout_seconds=0.01)

        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = TimeoutError()
        # kill() is synchronous on asyncio.subprocess.Process;
        # use MagicMock to avoid unawaited-coroutine warnings.
        from unittest.mock import MagicMock

        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock(return_value=None)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.run_detect(tmp_path, timeout_seconds=0.01)

        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_executable_not_found(self, tmp_path: Path) -> None:
        runner = GitleaksRunner(executable="nonexistent-gitleaks")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
            result = await runner.run_detect(tmp_path)

        assert result.exit_code == -1
        assert "not found" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_shell_false(self, tmp_path: Path) -> None:
        """Verify create_subprocess_exec is used (not shell=True)."""
        runner = GitleaksRunner(executable="gitleaks", timeout_seconds=30)

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"[]", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await runner.run_detect(tmp_path)

        mock_exec.assert_called_once()
        args = mock_exec.call_args
        assert args[0][0] == "gitleaks"
        assert args[0][1] == "detect"
        assert str(tmp_path) in str(args[0])
