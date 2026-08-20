"""Grype scanner runner — safe execution of the Syft + Grype pipeline.

This module runs two CLI tools in sequence:

1. **Syft** — generates a CycloneDX JSON SBOM from the repository workspace.
2. **Grype** — matches the SBOM against known vulnerabilities.

All command construction uses explicit argument arrays (no ``shell=True``).
Temporary SBOM files are created in a secure temp directory and always
deleted after use — even on failure or timeout.

Syft/Grype exit-code semantics:
- Syft 0: SBOM generated successfully
- Grype 0: no vulnerabilities found
- Grype 1: vulnerabilities found (NOT a scanner failure)
"""

import asyncio
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Exit code that means "vulnerabilities found" — not a scanner failure.
_VULNS_FOUND_EXIT_CODE = 1


@dataclass(frozen=True)
class SyftResult:
    """Raw result from a Syft execution."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class GrypeResult:
    """Raw result from a Grype execution."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def vulnerabilities_found(self) -> bool:
        """True when Grype exited with code 1 (vulns detected)."""
        return self.exit_code == _VULNS_FOUND_EXIT_CODE

    @property
    def success(self) -> bool:
        """True on exit code 0 (clean) or 1 (vulns found)."""
        return self.exit_code in (0, _VULNS_FOUND_EXIT_CODE)


class GrypeRunner:
    """Execute the Syft → Grype pipeline safely.

    Uses ``create_subprocess_exec`` with explicit argument arrays —
    never ``shell=True``.  Temporary SBOM files are always cleaned up.
    """

    def __init__(
        self,
        *,
        syft_executable: str = "syft",
        grype_executable: str = "grype",
        syft_timeout_seconds: float = 120.0,
        grype_timeout_seconds: float = 120.0,
    ) -> None:
        self._syft_executable = syft_executable
        self._grype_executable = grype_executable
        self._syft_timeout = max(0.1, syft_timeout_seconds)
        self._grype_timeout = max(0.1, grype_timeout_seconds)

    @staticmethod
    def is_available(executable: str) -> bool:
        """Check whether a binary is installed and reachable."""
        return shutil.which(executable) is not None

    @staticmethod
    def get_version(executable: str) -> str | None:
        """Return the installed version, or None if unavailable."""
        path = shutil.which(executable)
        if path is None:
            return None
        try:
            result = asyncio.get_event_loop().run_until_complete(_run_version_check(path))
            return result
        except Exception:
            try:
                import subprocess

                proc = subprocess.run(
                    [path, "version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                line = proc.stdout.strip()
                if line:
                    parts = line.split()
                    return parts[-1] if parts else None
                return None
            except (subprocess.TimeoutExpired, OSError):
                return None

    async def run_syft(
        self,
        source: Path,
        *,
        timeout_seconds: float | None = None,
    ) -> tuple[SyftResult, Path]:
        """Run ``syft`` to generate a CycloneDX JSON SBOM.

        Returns:
            A tuple of (SyftResult, path_to_sbom_file). The caller is
            responsible for deleting the SBOM file.
        """
        _validate_path(source)

        effective_timeout = timeout_seconds or self._syft_timeout

        # Create a temporary SBOM file — caller MUST delete it.
        sbom_fd, sbom_path_str = tempfile.mkstemp(
            suffix=".json",
            prefix="evoshield-sbom-",
        )
        sbom_path = Path(sbom_path_str)
        os.close(sbom_fd)

        proc = None
        try:
            # syft <source> -o cyclonedx-json=<file>
            args = [
                self._syft_executable,
                str(source),
                "-o",
                f"cyclonedx-json={sbom_path}",
            ]

            logger.info("Running Syft on %s", str(source)[:80])

            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=effective_timeout,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = proc.returncode or 0

            logger.info("Syft exited with code %d", exit_code)
            if stderr.strip():
                logger.debug("Syft stderr: %s", stderr[:500])

            return (
                SyftResult(exit_code=exit_code, stdout=stdout, stderr=stderr),
                sbom_path,
            )

        except TimeoutError:
            logger.warning("Syft timed out after %.1fs", effective_timeout)
            if proc is not None:
                proc.kill()
                await proc.wait()
            return (
                SyftResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Syft timed out after {effective_timeout:.0f}s",
                ),
                sbom_path,
            )
        except FileNotFoundError:
            return (
                SyftResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Syft executable not found: {self._syft_executable}",
                ),
                sbom_path,
            )
        except OSError as exc:
            logger.warning("Syft execution failed: %s", exc)
            return (
                SyftResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Failed to execute Syft: {exc}",
                ),
                sbom_path,
            )

    async def run_grype(
        self,
        sbom_path: Path,
        *,
        timeout_seconds: float | None = None,
    ) -> GrypeResult:
        """Run ``grype`` against a generated SBOM file.

        Args:
            sbom_path: Path to the CycloneDX JSON SBOM file.
            timeout_seconds: Override the default timeout.
        """
        if not _sbom_file_exists(sbom_path):
            return GrypeResult(
                exit_code=-1,
                stdout="",
                stderr=f"SBOM file does not exist: {sbom_path}",
            )

        effective_timeout = timeout_seconds or self._grype_timeout

        proc = None
        try:
            # grype sbom:<file> -o json
            args = [
                self._grype_executable,
                f"sbom:{sbom_path}",
                "-o",
                "json",
            ]

            logger.info("Running Grype against SBOM")

            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=effective_timeout,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = proc.returncode or 0

            logger.info("Grype exited with code %d", exit_code)
            if stderr.strip():
                logger.debug("Grype stderr: %s", stderr[:500])

            return GrypeResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
            )

        except TimeoutError:
            logger.warning("Grype timed out after %.1fs", effective_timeout)
            if proc is not None:
                proc.kill()
                await proc.wait()
            return GrypeResult(
                exit_code=-1,
                stdout="",
                stderr=f"Grype timed out after {effective_timeout:.0f}s",
            )
        except FileNotFoundError:
            return GrypeResult(
                exit_code=-1,
                stdout="",
                stderr=f"Grype executable not found: {self._grype_executable}",
            )
        except OSError as exc:
            logger.warning("Grype execution failed: %s", exc)
            return GrypeResult(
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute Grype: {exc}",
            )

    async def run_pipeline(
        self,
        source: Path,
        *,
        syft_timeout: float | None = None,
        grype_timeout: float | None = None,
    ) -> GrypeResult:
        """Run the full Syft → Grype pipeline.

        Generates an SBOM with Syft, then runs Grype against it.
        The SBOM file is always deleted after use.

        Returns:
            GrypeResult with the Grype output (vulnerability findings).
        """
        sbom_path: Path | None = None
        try:
            syft_result, sbom_path = await self.run_syft(source, timeout_seconds=syft_timeout)

            if not syft_result.success:
                # SECURITY: Never include raw stderr in application errors.
                logger.warning("Syft failed with exit code %d", syft_result.exit_code)
                return GrypeResult(
                    exit_code=syft_result.exit_code,
                    stdout="",
                    stderr="",
                )

            return await self.run_grype(sbom_path, timeout_seconds=grype_timeout)

        finally:
            # SECURITY: Always delete the SBOM file — it may contain
            # detailed dependency inventory.  Do this on every code path.
            if sbom_path is not None:
                _delete_sbom_file(sbom_path)


def _validate_path(path: Path) -> None:
    """Validate that a path is safe for scanning.

    Checks:
    - Path is absolute
    - Path exists
    - Path is a directory

    Raises:
        ValueError: If the path fails validation.
    """
    if not path.is_absolute():
        raise ValueError(f"Path must be absolute: {path}")
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")


def _sbom_file_exists(path: Path) -> bool:
    """Check if an SBOM file exists (sync helper for async context)."""
    try:
        return path.is_file()
    except OSError:
        return False


def _delete_sbom_file(path: Path) -> None:
    """Delete an SBOM file synchronously (security: must always clean up)."""
    try:
        if path.exists():
            path.unlink()
            logger.debug("Deleted SBOM file: %s", path)
    except OSError:
        logger.warning("Failed to delete SBOM file: %s", path)


async def _run_version_check(path: str) -> str | None:
    """Run a tool's version command asynchronously."""
    proc = await asyncio.create_subprocess_exec(
        path,
        "version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
    line = stdout_bytes.decode("utf-8", errors="replace").strip()
    if line:
        parts = line.split()
        return parts[-1] if parts else None
    return None
