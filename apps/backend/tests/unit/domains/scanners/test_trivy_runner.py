"""TrivyRunner unit tests.

Tests the subprocess runner with mocked execution — no real Trivy binary.
Verifies:
- Availability detection
- Version detection
- Path validation
- Command argument safety
- Timeout handling
- Exit code handling
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.domains.scanners.providers.trivy.runner import TrivyResult, TrivyRunner


class TestTrivyRunnerAvailability:
    """Test Trivy availability detection."""

    def test_is_available_when_in_path(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/trivy"):
            assert TrivyRunner.is_available() is True

    def test_is_not_available_when_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            assert TrivyRunner.is_available() is False


class TestTrivyRunnerVersion:
    """Test version detection."""

    def test_get_version_returns_version(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"TrivyVersion": "0.52.0"})
        with (
            patch("shutil.which", return_value="/usr/bin/trivy"),
            patch("subprocess.run", return_value=mock_result),
        ):
            version = TrivyRunner.get_version()
            assert version == "0.52.0"

    def test_get_version_returns_none_when_unavailable(self) -> None:
        with patch("shutil.which", return_value=None):
            assert TrivyRunner.get_version() is None

    def test_get_version_returns_none_on_error(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/trivy"),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("trivy", 10)),
        ):
            assert TrivyRunner.get_version() is None


class TestTrivyRunnerPathValidation:
    """Test path validation for security."""

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_path(self) -> None:
        runner = TrivyRunner()
        with pytest.raises(ValueError, match="does not exist"):
            await runner.run_filesystem(Path("/nonexistent/path"))

    @pytest.mark.asyncio
    async def test_rejects_relative_path(self) -> None:
        runner = TrivyRunner()
        with pytest.raises(ValueError, match="must be absolute"):
            await runner.run_filesystem(Path("relative/path"))

    @pytest.mark.asyncio
    async def test_rejects_file_not_directory(self, tmp_path: Path) -> None:
        runner = TrivyRunner()
        test_file = tmp_path / "test.txt"
        test_file.write_text("not a directory")
        with pytest.raises(ValueError, match="not a directory"):
            await runner.run_filesystem(test_file)


class TestTrivyResult:
    """Test TrivyResult data class."""

    def test_success_on_zero_exit(self) -> None:
        result = TrivyResult(exit_code=0, stdout="{}", stderr="")
        assert result.success is True

    def test_failure_on_nonzero_exit(self) -> None:
        result = TrivyResult(exit_code=1, stdout="", stderr="error")
        assert result.success is False

    def test_json_data_parses_valid_json(self) -> None:
        result = TrivyResult(exit_code=0, stdout='{"key": "value"}', stderr="")
        assert result.json_data == {"key": "value"}

    def test_json_data_returns_none_on_invalid(self) -> None:
        result = TrivyResult(exit_code=0, stdout="not json", stderr="")
        assert result.json_data is None

    def test_json_data_returns_none_on_empty(self) -> None:
        result = TrivyResult(exit_code=0, stdout="", stderr="")
        assert result.json_data is None
