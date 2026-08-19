"""Gitleaks subprocess runner — safe execution of the Gitleaks CLI.

All command construction uses explicit argument arrays (no shell=True).
Untrusted inputs (repository paths, names) are never concatenated into
shell commands.  The runner captures stdout, stderr, and exit code.

Gitleaks exit-code semantics:
- 0: no secrets found
- 1: secrets found (NOT a scanner failure)
- 2+: execution errors

Security measures:
- ``asyncio.create_subprocess_exec`` (not ``shell=True``)
- Explicit argument arrays — no shell interpretation
- Path validation before execution
- Timeout enforcement via ``asyncio.wait_for``
- Report file created in a secure temporary directory, deleted after parsing
"""

import asyncio
import json
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Exit code that means "secrets found" — not a scanner failure.
_SECRETS_FOUND_EXIT_CODE = 1


@dataclass(frozen=True)
class GitleaksResult:
    """Raw result from a Gitleaks execution."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def secrets_found(self) -> bool:
        """True when Gitleaks exited with code 1 (secrets detected)."""
        return self.exit_code == _SECRETS_FOUND_EXIT_CODE

    @property
    def success(self) -> bool:
        """True on exit code 0 (clean) or 1 (secrets found)."""
        return self.exit_code in (0, _SECRETS_FOUND_EXIT_CODE)

    @property
    def json_data(self) -> list[dict] | None:
        """Parse stdout as a JSON array of findings, or None if invalid."""
        if not self.stdout.strip():
            return []
        try:
            data = json.loads(self.stdout)
            # Gitleaks returns a JSON array of finding objects.
            if isinstance(data, list):
                return data
            # Some versions wrap in {"findings": [...]}.
            if isinstance(data, dict):
                return data.get("findings") or []
            return None
        except (json.JSONDecodeError, TypeError):
            logger.warning("Gitleaks produced invalid JSON output")
            return None


class GitleaksRunner:
    """Execute Gitleaks CLI commands safely.

    Uses ``create_subprocess_exec`` with explicit argument arrays —
    never ``shell=True``.  Repository paths are validated before use.
    """

    def __init__(
        self,
        *,
        executable: str = "gitleaks",
        timeout_seconds: float = 120.0,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = max(0.1, timeout_seconds)

    @staticmethod
    def is_available(executable: str = "gitleaks") -> bool:
        """Check whether Gitleaks is installed and reachable."""
        return shutil.which(executable) is not None

    @staticmethod
    def get_version(executable: str = "gitleaks") -> str | None:
        """Return the installed Gitleaks version, or None if unavailable."""
        path = shutil.which(executable)
        if path is None:
            return None
        try:
            result = asyncio.get_event_loop().run_until_complete(_run_version_check(path))
            return result
        except Exception:
            # Fallback: synchronous check.
            try:
                import subprocess

                proc = subprocess.run(
                    [path, "version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                # Gitleaks prints "gitleaks version X.Y.Z"
                line = proc.stdout.strip()
                if line:
                    parts = line.split()
                    return parts[-1] if parts else None
                return None
            except (subprocess.TimeoutExpired, OSError):
                return None

    async def run_detect(
        self,
        source: Path,
        *,
        timeout_seconds: float | None = None,
    ) -> GitleaksResult:
        """Run ``gitleaks detect`` on the given source path.

        Args:
            source: Directory to scan (must exist and be a directory).
            timeout_seconds: Override the default timeout.

        Returns:
            GitleaksResult with stdout, stderr, and exit_code.

        Raises:
            ValueError: If path does not exist or is not a directory.
        """
        self._validate_path(source)

        effective_timeout = timeout_seconds or self._timeout_seconds

        # Create a temporary report file — cleaned up after parsing.
        report_fd, report_path_str = tempfile.mkstemp(
            suffix=".json",
            prefix="gitleaks-report-",
        )
        report_path = Path(report_path_str)
        import os

        os.close(report_fd)

        try:
            # gitleaks detect --source <path> --report-format json --report-path <file>
            args = [
                self._executable,
                "detect",
                "--source",
                str(source),
                "--report-format",
                "json",
                "--report-path",
                str(report_path),
                "--no-banner",
            ]

            logger.info(
                "Running Gitleaks: %s",
                " ".join(args[:4]) + " ...",
            )

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

            # When Gitleaks writes to --report-path, stdout may be empty.
            # Read the report file instead (sync I/O in a local helper).
            report_content = _read_report_file(report_path)

            # Use report content as stdout if stdout is empty.
            effective_stdout = stdout if stdout.strip() else report_content

            logger.info("Gitleaks exited with code %d", exit_code)
            if stderr.strip():
                logger.debug("Gitleaks stderr: %s", stderr[:500])

            return GitleaksResult(
                exit_code=exit_code,
                stdout=effective_stdout,
                stderr=stderr,
            )

        except TimeoutError:
            logger.warning("Gitleaks timed out after %.1fs", effective_timeout)
            if proc is not None:
                proc.kill()
                await proc.wait()
            return GitleaksResult(
                exit_code=-1,
                stdout="",
                stderr=f"Gitleaks timed out after {effective_timeout:.0f}s",
            )
        except FileNotFoundError:
            return GitleaksResult(
                exit_code=-1,
                stdout="",
                stderr=f"Gitleaks executable not found: {self._executable}",
            )
        except OSError as exc:
            logger.warning("Gitleaks execution failed: %s", exc)
            return GitleaksResult(
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute Gitleaks: {exc}",
            )
        finally:
            # SECURITY: Always delete the report file — it may contain
            # secret values.  Do this on every code path.
            _delete_report_file(report_path)

    @staticmethod
    def _validate_path(path: Path) -> None:
        """Validate that a path is safe for scanning.

        Checks:
        - Path is absolute (prevents relative traversal)
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


def _read_report_file(path: Path) -> str:
    """Read a report file synchronously (sync I/O outside async context)."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return ""


def _delete_report_file(path: Path) -> None:
    """Delete a report file synchronously (security: must always clean up)."""
    try:
        if path.exists():
            path.unlink()
    except OSError:
        logger.warning("Failed to delete Gitleaks report file: %s", path)


async def _run_version_check(path: str) -> str | None:
    """Run gitleaks version asynchronously."""
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
