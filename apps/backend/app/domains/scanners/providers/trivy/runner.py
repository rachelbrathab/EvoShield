"""Trivy subprocess runner — safe execution of the Trivy CLI.

All command construction uses explicit argument arrays (no shell=True).
Untrusted inputs (repository paths, names) are never concatenated into
shell commands.  The runner captures stdout, stderr, and exit code.

Security measures:
- `subprocess.create_subprocess_exec` (not `shell=True`)
- Explicit argument arrays — no shell interpretation
- Path validation before execution
- Timeout enforcement via asyncio.wait_for
"""

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrivyResult:
    """Raw result from a Trivy execution."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def json_data(self) -> dict | None:
        """Parse stdout as JSON, or None if invalid."""
        if not self.stdout.strip():
            return None
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError:
            logger.warning("Trivy produced invalid JSON output")
            return None


class TrivyRunner:
    """Execute Trivy CLI commands safely.

    Uses `create_subprocess_exec` with explicit argument arrays —
    never shell=True.  Repository paths are validated before use.
    """

    def __init__(
        self,
        *,
        executable: str = "trivy",
        timeout_seconds: float = 120.0,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = max(0.1, timeout_seconds)

    @staticmethod
    def is_available(executable: str = "trivy") -> bool:
        """Check whether Trivy is installed and reachable."""
        return shutil.which(executable) is not None

    @staticmethod
    def get_version(executable: str = "trivy") -> str | None:
        """Return the installed Trivy version, or None if unavailable."""
        path = shutil.which(executable)
        if path is None:
            return None
        try:
            import subprocess

            result = subprocess.run(
                [path, "version", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return None
            data = json.loads(result.stdout)
            # Trivy version JSON structure: {"SchemaVersion": "...", "TrivyVersion": "..."}
            return data.get("TrivyVersion") or data.get("Version")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return None

    async def run_filesystem(
        self,
        path: Path,
        *,
        timeout_seconds: float | None = None,
    ) -> TrivyResult:
        """Run a Trivy filesystem scan on the given path.

        Args:
            path: Directory to scan (must exist and be a directory).
            timeout_seconds: Override the default timeout.

        Returns:
            TrivyResult with stdout, stderr, and exit_code.

        Raises:
            ValueError: If path does not exist or is not a directory.
        """
        self._validate_path(path)

        effective_timeout = timeout_seconds or self._timeout_seconds

        # Build command: trivy fs --format json --scanners vuln,secret <path>
        # --scanners restricts to vulnerability and secret scanning
        args = [
            self._executable,
            "fs",
            "--format",
            "json",
            "--scanners",
            "vuln",
            "--offline-scan",
            "--skip-db-update",
            str(path),
        ]

        logger.info("Running Trivy: %s", " ".join(args))

        try:
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

            logger.info("Trivy exited with code %d", exit_code)
            if stderr.strip():
                logger.debug("Trivy stderr: %s", stderr[:500])

            return TrivyResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
            )

        except TimeoutError:
            logger.warning("Trivy timed out after %.1fs", effective_timeout)
            if proc is not None:
                proc.kill()
                await proc.wait()
            return TrivyResult(
                exit_code=-1,
                stdout="",
                stderr=f"Trivy timed out after {effective_timeout:.0f}s",
            )
        except FileNotFoundError:
            return TrivyResult(
                exit_code=-1,
                stdout="",
                stderr=f"Trivy executable not found: {self._executable}",
            )
        except OSError as exc:
            logger.warning("Trivy execution failed: %s", exc)
            return TrivyResult(
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute Trivy: {exc}",
            )

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
