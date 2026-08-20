"""Semgrep subprocess runner — safe execution of the Semgrep CLI.

All command construction uses explicit argument arrays (no shell=True).
Untrusted inputs (repository paths, names) are never concatenated into
shell commands.  The runner captures stdout, stderr, and exit code.

Semgrep exit-code semantics (from semgrep --help / docs):
- 0: no findings
- 1: findings detected (NOT a scanner failure)
- 2+: execution error

Security measures:
- ``asyncio.create_subprocess_exec`` (not ``shell=True``)
- Explicit argument arrays — no shell interpretation
- Path validation before execution
- Timeout enforcement via ``asyncio.wait_for``
- Output size limits to prevent memory exhaustion
"""

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum stdout size we'll accept from Semgrep (10 MB).
_MAX_OUTPUT_BYTES = 10 * 1024 * 1024

# Exit code that means "findings detected" — not a scanner failure.
_FINDINGS_FOUND_EXIT_CODE = 1


@dataclass(frozen=True)
class SemgrepResult:
    """Raw result from a Semgrep execution."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def findings_found(self) -> bool:
        """True when Semgrep exited with code 1 (findings detected)."""
        return self.exit_code == _FINDINGS_FOUND_EXIT_CODE

    @property
    def success(self) -> bool:
        """True on exit code 0 (clean) or 1 (findings found)."""
        return self.exit_code in (0, _FINDINGS_FOUND_EXIT_CODE)

    @property
    def json_data(self) -> dict | None:
        """Parse stdout as Semgrep JSON output, or None if invalid."""
        if not self.stdout.strip():
            return {}
        try:
            data = json.loads(self.stdout)
            if isinstance(data, dict):
                return data
            return None
        except (json.JSONDecodeError, TypeError):
            logger.warning("Semgrep produced invalid JSON output")
            return None


class SemgrepRunner:
    """Execute Semgrep CLI commands safely.

    Uses ``create_subprocess_exec`` with explicit argument arrays —
    never ``shell=True``.  Repository paths are validated before use.
    """

    def __init__(
        self,
        *,
        executable: str = "semgrep",
        timeout_seconds: float = 120.0,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = max(0.1, timeout_seconds)

    @staticmethod
    def is_available(executable: str = "semgrep") -> bool:
        """Check whether Semgrep is installed and reachable."""
        return shutil.which(executable) is not None

    @staticmethod
    def get_version(executable: str = "semgrep") -> str | None:
        """Return the installed Semgrep version, or None if unavailable."""
        path = shutil.which(executable)
        if path is None:
            return None
        try:
            import subprocess

            proc = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Semgrep prints "semgrep X.Y.Z" or similar.
            line = proc.stdout.strip()
            if line:
                parts = line.split()
                return parts[-1] if len(parts) > 1 else line
            return None
        except (subprocess.TimeoutExpired, OSError):
            return None

    async def run_scan(
        self,
        source: Path,
        *,
        timeout_seconds: float | None = None,
        config: str = "auto",
    ) -> SemgrepResult:
        """Run ``semgrep scan`` on the given source path.

        Args:
            source: Directory to scan (must exist and be a directory).
            timeout_seconds: Override the default timeout.
            config: Semgrep rules config. Default ``"auto"`` uses
                the Semgrep registry for security rules.

        Returns:
            SemgrepResult with stdout, stderr, and exit_code.

        Raises:
            ValueError: If path does not exist or is not a directory.
        """
        self._validate_path(source)

        effective_timeout = timeout_seconds or self._timeout_seconds

        # semgrep scan --json --config auto <path>
        args = [
            self._executable,
            "scan",
            "--json",
            "--config",
            config,
            "--quiet",
            str(source),
        ]

        logger.info(
            "Running Semgrep: %s",
            " ".join(args[:5]) + " ...",
        )

        proc: asyncio.subprocess.Process | None = None
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

            # Enforce output size limit to prevent memory exhaustion.
            if len(stdout_bytes) > _MAX_OUTPUT_BYTES:
                logger.warning(
                    "Semgrep output truncated: %d bytes > %d byte limit",
                    len(stdout_bytes),
                    _MAX_OUTPUT_BYTES,
                )
                stdout_bytes = stdout_bytes[:_MAX_OUTPUT_BYTES]

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = proc.returncode or 0

            logger.info("Semgrep exited with code %d", exit_code)
            if stderr.strip():
                logger.debug("Semgrep stderr: %s", stderr[:500])

            return SemgrepResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
            )

        except TimeoutError:
            logger.warning("Semgrep timed out after %.1fs", effective_timeout)
            if proc is not None:
                proc.kill()
                await proc.wait()
            return SemgrepResult(
                exit_code=-1,
                stdout="",
                stderr=f"Semgrep timed out after {effective_timeout:.0f}s",
            )
        except FileNotFoundError:
            return SemgrepResult(
                exit_code=-1,
                stdout="",
                stderr=f"Semgrep executable not found: {self._executable}",
            )
        except OSError as exc:
            logger.warning("Semgrep execution failed: %s", exc)
            return SemgrepResult(
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute Semgrep: {exc}",
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
