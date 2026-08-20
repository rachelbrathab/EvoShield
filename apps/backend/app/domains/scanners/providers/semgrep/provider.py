"""Semgrep analysis provider — SAST (Static Application Security Testing) adapter.

Implements the ``AnalysisProvider`` port from the analysis domain, bridging
the analysis orchestrator to the Semgrep CLI.  Scanner-specific logic stays
entirely inside this module:

- ``GitHubRepositorySource`` acquires the repository checkout
- ``SemgrepRunner`` executes the CLI safely (no shell=True, argument arrays)
- ``SemgrepResultParser`` normalizes JSON output into ``ScannerFinding`` objects

The orchestrator calls ``execute(context)`` — it never knows about Semgrep.

SECURITY: Source code snippets from Semgrep output are NOT persisted.
Only safe metadata (rule ID, file, line, severity, CWE/OWASP) is retained.
"""

import logging
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.domains.analysis.ports import AnalysisCancelledError, AnalysisExecutionContext
from app.domains.scanners.providers.github_source import (
    GitHubRepositorySource,
    RepositoryAcquisitionError,
    WorkspaceHandle,
)
from app.domains.scanners.providers.semgrep.parser import SemgrepResultParser
from app.domains.scanners.providers.semgrep.runner import SemgrepRunner

logger = logging.getLogger(__name__)


class SemgrepProvider:
    """Semgrep SAST analysis provider.

    Implements ``AnalysisProvider`` protocol so the orchestrator can dispatch
    it as a drop-in scanner alongside Trivy and Gitleaks.
    """

    name = "semgrep"
    version = "0.1.0"

    def __init__(
        self,
        *,
        executable: str = "semgrep",
        timeout_seconds: float = 120.0,
        findings_callback: Any = None,
        git_executable: str = "git",
        max_repository_size_mb: float = 500.0,
        repository_clone_timeout_seconds: float = 120.0,
        semgrep_config: str = "auto",
    ) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._git_executable = git_executable
        self._max_repository_size_mb = max_repository_size_mb
        self._repository_clone_timeout_seconds = repository_clone_timeout_seconds
        self._semgrep_config = semgrep_config
        self._runner = SemgrepRunner(
            executable=executable,
            timeout_seconds=timeout_seconds,
        )
        self._parser = SemgrepResultParser(
            scanner_name=self.name,
            scanner_version=self.version,
        )
        # Callback invoked after successful scan to persist findings.
        self._findings_callback = findings_callback

    def supports(self, repository: Any) -> bool:
        """Semgrep can scan any non-archived, non-disabled repository."""
        if hasattr(repository, "archived") and repository.archived:
            return False
        if hasattr(repository, "disabled") and repository.disabled:
            return False
        return True

    async def execute(self, context: AnalysisExecutionContext) -> None:
        """Execute a Semgrep SAST scan with repository acquisition.

        Pipeline:
        1. Validate Semgrep is available
        2. Acquire repository via GitHub API
        3. Run Semgrep scan on the cloned checkout
        4. Parse JSON output (source snippets discarded)
        5. Normalize findings
        6. Persist findings
        7. Clean up workspace

        Raises:
            AnalysisCancelledError: If the cancel event is set.
            ProviderError: If any step fails.
        """
        if context.cancel_event.is_set():
            raise AnalysisCancelledError("analysis cancelled before execution")

        # Validate Semgrep is available
        if not SemgrepRunner.is_available(self._executable):
            raise ProviderError(
                f"Semgrep is not installed or not available in PATH "
                f"(executable: {self._executable}). "
                "Install Semgrep: https://semgrep.dev/",
                code="scanner_unavailable",
            )

        version = SemgrepRunner.get_version(self._executable)
        logger.info(
            "Starting Semgrep scan for %s (version=%s, run=%s)",
            context.full_name,
            version,
            context.run_id,
        )

        # Acquire repository source via GitHub
        workspace: WorkspaceHandle | None = None
        try:
            workspace = await self._acquire_repository(context)

            if context.cancel_event.is_set():
                raise AnalysisCancelledError("analysis cancelled after acquisition")

            # Execute Semgrep on the cloned checkout
            repo_path = workspace.repo_path
            result = await self._runner.run_scan(
                repo_path,
                timeout_seconds=self._timeout_seconds,
                config=self._semgrep_config,
            )

            if context.cancel_event.is_set():
                raise AnalysisCancelledError("analysis cancelled after scan")

            if not result.success:
                # Exit code 1 = findings detected (NOT a failure).
                # Exit code 2+ = execution error.
                # SECURITY: Never include raw stderr — it may contain
                # source code content or sensitive repository information.
                raise ProviderError(
                    f"Semgrep scan failed with exit code {result.exit_code}.",
                    code="scanner_execution_failed",
                )

            # Parse the output — source snippets are DISCARDED by the parser.
            findings = self._parser.parse(
                result.stdout,
                analysis_run_id=context.run_id,
            )

            logger.info(
                "Semgrep scan complete: %d SAST findings for %s (run=%s)",
                len(findings),
                context.full_name,
                context.run_id,
            )

            # Persist findings
            if self._findings_callback is not None:
                await self._findings_callback(findings)

        except AnalysisCancelledError:
            raise
        except ProviderError:
            raise
        except RepositoryAcquisitionError as exc:
            code = getattr(exc, "code", "acquisition_failed")
            raise ProviderError(
                str(exc),
                code=code,
            ) from exc
        finally:
            # Always clean up the workspace
            if workspace is not None:
                workspace.cleanup()

    async def _acquire_repository(
        self,
        context: AnalysisExecutionContext,
    ) -> WorkspaceHandle:
        """Acquire the repository checkout into a temporary workspace."""
        settings = get_settings()
        source = GitHubRepositorySource(
            token_resolver=context.token_resolver,
            executable=settings.git_executable,
            max_repository_size_mb=settings.repository_max_size_mb,
            timeout_seconds=settings.repository_clone_timeout_seconds,
        )

        try:
            workspace = await source.acquire(
                context.full_name,
                branch=None,
            )

            repo_size_mb = _directory_size_mb(workspace.repo_path)
            max_mb = settings.repository_max_size_mb
            if repo_size_mb > max_mb:
                workspace.cleanup()
                raise ProviderError(
                    f"Repository is too large ({repo_size_mb:.0f}MB > {max_mb:.0f}MB limit).",
                    code="repository_too_large",
                )

            return workspace

        except RepositoryAcquisitionError as exc:
            code = getattr(exc, "code", "acquisition_failed")
            if code == "github_not_connected":
                raise ProviderError(
                    "Connect your GitHub account to run analysis.",
                    code="github_not_connected",
                ) from exc
            if code == "github_token_invalid":
                raise ProviderError(
                    "Your GitHub connection is invalid or expired. Reconnect your account.",
                    code="github_token_invalid",
                ) from exc
            if code == "acquisition_failed":
                raise ProviderError(
                    "Failed to download the repository. It may be unavailable or the "
                    "access token may lack permissions.",
                    code="acquisition_failed",
                ) from exc
            raise ProviderError(
                f"Repository acquisition failed: {exc}",
                code=code,
            ) from exc


def _directory_size_mb(path: Any) -> float:
    """Approximate directory size in megabytes."""
    from pathlib import Path

    total = 0
    try:
        for entry in Path(path).rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except OSError:
        pass
    return total / (1024 * 1024)
