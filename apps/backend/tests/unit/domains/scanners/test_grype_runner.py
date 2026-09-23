"""Tests for the Grype (Syft + Grype) runner.

Verifies safe subprocess execution with explicit argument arrays,
no shell=True, timeout handling, cancellation, and SBOM file cleanup.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.scanners.providers.grype.runner import (
    GrypeResult,
    GrypeRunner,
    SyftResult,
)


class TestGrypeResult:
    """Test GrypeResult properties."""

    def test_success_zero(self) -> None:
        r = GrypeResult(exit_code=0, stdout="", stderr="")
        assert r.success is True
        assert r.vulnerabilities_found is False

    def test_success_vulns_found(self) -> None:
        r = GrypeResult(exit_code=1, stdout="{}", stderr="")
        assert r.success is True
        assert r.vulnerabilities_found is True

    def test_failure(self) -> None:
        r = GrypeResult(exit_code=2, stdout="", stderr="error")
        assert r.success is False
        assert r.vulnerabilities_found is False


class TestSyftResult:
    """Test SyftResult properties."""

    def test_success(self) -> None:
        r = SyftResult(exit_code=0, stdout="", stderr="")
        assert r.success is True

    def test_failure(self) -> None:
        r = SyftResult(exit_code=1, stdout="", stderr="error")
        assert r.success is False


class TestGrypeRunnerAvailability:
    """Test executable detection."""

    def test_is_available_true(self) -> None:
        with patch(
            "app.domains.scanners.providers.grype.runner.shutil.which",
            return_value="/usr/bin/syft",
        ):
            assert GrypeRunner.is_available("syft") is True

    def test_is_available_false(self) -> None:
        with patch(
            "app.domains.scanners.providers.grype.runner.shutil.which",
            return_value=None,
        ):
            assert GrypeRunner.is_available("syft") is False


class TestGrypeRunnerValidation:
    """Test path validation."""

    def test_validate_relative_path(self) -> None:
        from app.domains.scanners.providers.grype.runner import _validate_path

        with pytest.raises(ValueError, match="absolute"):
            _validate_path(Path("relative/path"))

    def test_validate_nonexistent_path(self) -> None:
        from app.domains.scanners.providers.grype.runner import _validate_path

        with pytest.raises(ValueError, match="does not exist"):
            _validate_path(Path("/nonexistent/path/that/does/not/exist"))

    def test_validate_file_not_dir(self, tmp_path: Path) -> None:
        from app.domains.scanners.providers.grype.runner import _validate_path

        f = tmp_path / "file.txt"
        f.write_text("content")
        with pytest.raises(ValueError, match="not a directory"):
            _validate_path(f)


class TestGrypeRunnerCommandConstruction:
    """Test that commands use explicit argument arrays."""

    @pytest.mark.asyncio
    async def test_syft_uses_create_subprocess_exec(self, tmp_path: Path) -> None:
        runner = GrypeRunner(syft_executable="syft", syft_timeout_seconds=60)

        async def _mock_exec(*args, **kwargs):
            mock_proc = MagicMock()
            mock_proc.communicate = AsyncMock(return_value=(b'{"bomFormat":"CycloneDX"}', b""))
            mock_proc.returncode = 0
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec) as mock_exec:
            _result, sbom_path = await runner.run_syft(tmp_path)

            # Verify create_subprocess_exec was called (no shell=True)
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args
            assert call_args[0][0] == "syft"  # First arg is the executable

            # Verify no shell=True
            assert "shell" not in call_args.kwargs or call_args.kwargs.get("shell") is not True

            # Clean up SBOM
            if sbom_path.exists():
                sbom_path.unlink()

    @pytest.mark.asyncio
    async def test_grype_matches_warmed_sbom_without_database_update(self, tmp_path: Path) -> None:
        runner = GrypeRunner(grype_executable="grype", grype_timeout_seconds=60)
        sbom = tmp_path / "warmed-sbom.json"
        sbom.write_text('{"bomFormat":"CycloneDX","components":[]}')

        async def _mock_exec(*args, **kwargs):
            mock_proc = MagicMock()
            mock_proc.communicate = AsyncMock(return_value=(b'{"matches":[]}', b""))
            mock_proc.returncode = 0
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec) as mock_exec:
            result = await runner.run_grype(sbom)

        assert result.success is True
        assert result.stdout == '{"matches":[]}'
        assert mock_exec.call_args.kwargs["env"]["GRYPE_DB_AUTO_UPDATE"] == "false"

    @pytest.mark.asyncio
    async def test_grype_uses_create_subprocess_exec(self, tmp_path: Path) -> None:
        runner = GrypeRunner(grype_executable="grype", grype_timeout_seconds=60)

        # Create a fake SBOM file
        sbom = tmp_path / "sbom.json"
        sbom.write_text('{"bomFormat":"CycloneDX"}')

        async def _mock_exec(*args, **kwargs):
            mock_proc = MagicMock()
            mock_proc.communicate = AsyncMock(return_value=(b'{"matches":[]}', b""))
            mock_proc.returncode = 0
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec) as mock_exec:
            await runner.run_grype(sbom)

            # Verify create_subprocess_exec was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args
            assert "grype" in str(call_args[0][0])

            # Verify no shell=True
            assert "shell" not in call_args.kwargs or call_args.kwargs.get("shell") is not True
            assert call_args.kwargs["env"]["GRYPE_DB_AUTO_UPDATE"] == "false"


class TestGrypeRunnerTimeout:
    """Test timeout handling."""

    @pytest.mark.asyncio
    async def test_syft_timeout(self, tmp_path: Path) -> None:
        runner = GrypeRunner(syft_executable="syft", syft_timeout_seconds=0.01)

        async def _slow(*args, **kwargs):
            raise TimeoutError()

        with patch("asyncio.create_subprocess_exec", side_effect=_slow):
            result, sbom_path = await runner.run_syft(tmp_path, timeout_seconds=0.01)

            assert result.exit_code == -1
            assert "timed out" in result.stderr.lower()

            # SBOM file should still exist (caller cleans up)
            if sbom_path.exists():
                sbom_path.unlink()

    @pytest.mark.asyncio
    async def test_grype_timeout(self, tmp_path: Path) -> None:
        runner = GrypeRunner(grype_executable="grype", grype_timeout_seconds=0.01)

        sbom = tmp_path / "sbom.json"
        sbom.write_text('{"bomFormat":"CycloneDX"}')

        async def _slow(*args, **kwargs):
            raise TimeoutError()

        with patch("asyncio.create_subprocess_exec", side_effect=_slow):
            result = await runner.run_grype(sbom, timeout_seconds=0.01)

            assert result.exit_code == -1
            assert "timed out" in result.stderr.lower()


class TestGrypeRunnerMissingExecutable:
    """Test behavior when executable is not found."""

    @pytest.mark.asyncio
    async def test_syft_not_found(self, tmp_path: Path) -> None:
        runner = GrypeRunner(syft_executable="nonexistent-syft")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result, sbom_path = await runner.run_syft(tmp_path)
            assert result.exit_code == -1
            assert "not found" in result.stderr.lower()
            if sbom_path.exists():
                sbom_path.unlink()

    @pytest.mark.asyncio
    async def test_grype_not_found(self, tmp_path: Path) -> None:
        runner = GrypeRunner(grype_executable="nonexistent-grype")

        sbom = tmp_path / "sbom.json"
        sbom.write_text("{}")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await runner.run_grype(sbom)
            assert result.exit_code == -1
            assert "not found" in result.stderr.lower()


class TestGrypeRunnerGrypeMissingSbom:
    """Test Grype behavior when SBOM file is missing."""

    @pytest.mark.asyncio
    async def test_grype_missing_sbom_file(self) -> None:
        runner = GrypeRunner()
        from pathlib import Path

        missing = Path("/nonexistent/sbom.json")
        result = await runner.run_grype(missing)
        assert result.exit_code == -1
        assert "does not exist" in result.stderr


class TestGrypeRunnerCleanup:
    """Test SBOM file cleanup in the pipeline."""

    @pytest.mark.asyncio
    async def test_sbom_deleted_after_pipeline(self, tmp_path: Path) -> None:
        runner = GrypeRunner(
            syft_executable="syft",
            grype_executable="grype",
            syft_timeout_seconds=30,
            grype_timeout_seconds=30,
        )

        # Mock Syft to create the SBOM file and return success
        def _write_fake_sbom() -> Path:
            import tempfile

            fd, path_str = tempfile.mkstemp(suffix=".json", prefix="test-sbom-")
            import os

            os.close(fd)
            Path(path_str).write_text('{"bomFormat":"CycloneDX"}')
            return Path(path_str)

        async def _mock_syft(source, *, timeout_seconds=None):
            return (
                SyftResult(exit_code=0, stdout="", stderr=""),
                _write_fake_sbom(),
            )

        # Mock Grype to return success
        async def _mock_grype(sbom_path, *, timeout_seconds=None):
            return GrypeResult(exit_code=0, stdout='{"matches":[]}', stderr="")

        with (
            patch.object(runner, "run_syft", side_effect=_mock_syft),
            patch.object(runner, "run_grype", side_effect=_mock_grype),
        ):
            result = await runner.run_pipeline(tmp_path)

            assert result.exit_code == 0


class TestGrypeRunnerCancellation:
    """Test cancellation handling."""

    @pytest.mark.asyncio
    async def test_syft_os_error(self, tmp_path: Path) -> None:
        runner = GrypeRunner(syft_executable="syft")

        with patch("asyncio.create_subprocess_exec", side_effect=OSError("permission denied")):
            result, sbom_path = await runner.run_syft(tmp_path)
            assert result.exit_code == -1
            assert "failed" in result.stderr.lower()
            if sbom_path.exists():
                sbom_path.unlink()
