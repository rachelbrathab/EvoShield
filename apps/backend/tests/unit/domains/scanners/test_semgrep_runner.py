"""Tests for the Semgrep subprocess runner.

Verifies safe command construction, timeout handling, exit-code semantics,
and path validation.  All tests use mocked subprocesses — no real Semgrep
binary required.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.scanners.providers.semgrep.runner import (
    SemgrepResult,
    SemgrepRunner,
)


class TestSemgrepResult:
    """Verify SemgrepResult dataclass behavior."""

    def test_success_on_exit_0(self) -> None:
        r = SemgrepResult(exit_code=0, stdout="[]", stderr="")
        assert r.success is True
        assert r.findings_found is False

    def test_success_on_exit_1(self) -> None:
        r = SemgrepResult(exit_code=1, stdout="{}", stderr="")
        assert r.success is True
        assert r.findings_found is True

    def test_failure_on_exit_2(self) -> None:
        r = SemgrepResult(exit_code=2, stdout="", stderr="error")
        assert r.success is False

    def test_json_data_valid(self) -> None:
        r = SemgrepResult(exit_code=1, stdout='{"results": []}', stderr="")
        assert r.json_data == {"results": []}

    def test_json_data_empty(self) -> None:
        r = SemgrepResult(exit_code=0, stdout="", stderr="")
        assert r.json_data == {}

    def test_json_data_invalid(self) -> None:
        r = SemgrepResult(exit_code=0, stdout="not json", stderr="")
        assert r.json_data is None


class TestSemgrepRunnerAvailability:
    """Verify static availability and version checks."""

    def test_is_available_when_found(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/semgrep"):
            assert SemgrepRunner.is_available() is True

    def test_is_available_when_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            assert SemgrepRunner.is_available() is False

    def test_get_version_when_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            assert SemgrepRunner.get_version() is None


class TestSemgrepRunnerValidation:
    """Verify path validation."""

    def test_rejects_relative_path(self, tmp_path: Path) -> None:
        runner = SemgrepRunner()
        with pytest.raises(ValueError, match="absolute"):
            runner._validate_path(Path("relative/path"))

    def test_rejects_nonexistent_path(self) -> None:
        runner = SemgrepRunner()
        with pytest.raises(ValueError, match="does not exist"):
            runner._validate_path(Path("/nonexistent/path/that/does/not/exist"))

    def test_rejects_file_not_directory(self, tmp_path: Path) -> None:
        marker = tmp_path / "file.txt"
        marker.write_text("not a directory")
        runner = SemgrepRunner()
        with pytest.raises(ValueError, match="not a directory"):
            runner._validate_path(marker)

    def test_accepts_valid_directory(self, tmp_path: Path) -> None:
        runner = SemgrepRunner()
        # Should not raise
        runner._validate_path(tmp_path)


class TestSemgrepRunnerExecution:
    """Verify run_scan with mocked subprocess."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, tmp_path: Path) -> None:
        runner = SemgrepRunner(executable="semgrep", timeout_seconds=30)

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b'{"results": []}', b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.run_scan(tmp_path)

        assert result.exit_code == 0
        assert result.success is True

    @pytest.mark.asyncio
    async def test_findings_exit_code(self, tmp_path: Path) -> None:
        runner = SemgrepRunner(executable="semgrep", timeout_seconds=30)

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            b'{"results": [{"check_id": "test"}]}',
            b"",
        )
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.run_scan(tmp_path)

        assert result.exit_code == 1
        assert result.success is True
        assert result.findings_found is True

    @pytest.mark.asyncio
    async def test_error_exit_code(self, tmp_path: Path) -> None:
        runner = SemgrepRunner(executable="semgrep", timeout_seconds=30)

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"fatal error")
        mock_proc.returncode = 2

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.run_scan(tmp_path)

        assert result.exit_code == 2
        assert result.success is False

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self, tmp_path: Path) -> None:
        runner = SemgrepRunner(executable="semgrep", timeout_seconds=0.01)

        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = TimeoutError()
        # kill() is synchronous on asyncio.subprocess.Process;
        # use MagicMock to avoid unawaited-coroutine warnings.
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock(return_value=None)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.run_scan(tmp_path, timeout_seconds=0.01)

        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_executable_not_found(self, tmp_path: Path) -> None:
        runner = SemgrepRunner(executable="nonexistent-semgrep")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
            result = await runner.run_scan(tmp_path)

        assert result.exit_code == -1
        assert "not found" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_os_error(self, tmp_path: Path) -> None:
        runner = SemgrepRunner(executable="semgrep", timeout_seconds=30)

        with patch("asyncio.create_subprocess_exec", side_effect=OSError("permission denied")):
            result = await runner.run_scan(tmp_path)

        assert result.exit_code == -1
        assert "failed to execute" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_command_arguments(self, tmp_path: Path) -> None:
        """Verify the exact arguments passed to create_subprocess_exec."""
        runner = SemgrepRunner(executable="semgrep", timeout_seconds=30)

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"{}", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await runner.run_scan(tmp_path, config="p/security-audit")

        call_args = mock_exec.call_args
        args = call_args[0]
        assert args[0] == "semgrep"
        assert args[1] == "scan"
        assert "--json" in args
        assert "--config" in args
        assert "p/security-audit" in args
        assert "--quiet" in args
        assert str(tmp_path) in args

    @pytest.mark.asyncio
    async def test_no_shell_true(self, tmp_path: Path) -> None:
        """Verify shell=True is never passed."""
        runner = SemgrepRunner(executable="semgrep", timeout_seconds=30)

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"{}", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await runner.run_scan(tmp_path)

        call_kwargs = mock_exec.call_args[1]
        assert "shell" not in call_kwargs or call_kwargs.get("shell") is not True
