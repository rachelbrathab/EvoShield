"""Trivy analysis provider — the first real scanner adapter.

Implements the `AnalysisProvider` port from the analysis domain, bridging
the analysis orchestrator to the Trivy CLI.  Scanner-specific logic stays
entirely inside this module:

- ``GitHubRepositorySource`` acquires the repository checkout
- ``TrivyRunner`` executes the CLI safely (no shell=True, argument arrays)
- ``TrivyResultParser`` normalizes JSON output into ``ScannerFinding`` objects
- Findings are persisted to the database after successful execution

The orchestrator calls ``execute(context)`` — it never knows about Trivy.

Sprint 5B adds the full acquisition pipeline:

1. The orchestrator provides an ``AnalysisExecutionContext`` with an
   ``owner_id`` and ``token_resolver``.
2. The provider uses ``GitHubRepositorySource`` to clone the repository
   into a temporary workspace.
3. Trivy runs a filesystem scan against the cloned checkout.
4. Results are parsed, normalized, and persisted as findings.
5. The temporary workspace is cleaned up (success or failure).
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
from app.domains.scanners.providers.trivy.parser import TrivyResultParser
from app.domains.scanners.providers.trivy.runner import TrivyRunner

logger = logging.getLogger(__name__)


class TrivyProvider:
    """Trivy analysis provider — the first real scanner.

    Implements ``AnalysisProvider`` protocol (from analysis domain) so the
    orchestrator can dispatch it as a drop-in replacement for the fake.
    """

    name = "trivy"
    version = "0.1.0"

    def __init__(
        self,
        *,
        executable: str = "trivy",
        timeout_seconds: float = 120.0,
        findings_callback: Any = None,
        git_executable: str = "git",
        max_repository_size_mb: float = 500.0,
        repository_clone_timeout_seconds: float = 120.0,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._git_executable = git_executable
        self._max_repository_size_mb = max_repository_size_mb
        self._repository_clone_timeout_seconds = repository_clone_timeout_seconds
        self._runner = TrivyRunner(
            executable=executable,
            timeout_seconds=timeout_seconds,
        )
        self._parser = TrivyResultParser(
            scanner_name=self.name,
            scanner_version=self.version,
        )
        # Callback invoked after successful scan to persist findings.
        # Signature: async def callback(findings: list[ScannerFinding]) -> None
        self._findings_callback = findings_callback

    def supports(self, repository: Any) -> bool:
        """Trivy can scan any repository that is not archived or disabled."""
        if hasattr(repository, "archived") and repository.archived:
            return False
        if hasattr(repository, "disabled") and repository.disabled:
            return False
        return True

    async def execute(self, context: AnalysisExecutionContext) -> None:
        """Execute a Trivy filesystem scan with repository acquisition.

        The full pipeline:
        1. Validate Trivy is available
        2. Acquire repository via GitHub API (clone into temp workspace)
        3. Run Trivy filesystem scan on the cloned checkout
        4. Parse JSON output
        5. Normalize findings
        6. Persist findings
        7. Clean up workspace

        Raises:
            AnalysisCancelledError: If the cancel event is set.
            ProviderError: If any step in the pipeline fails.
        """
        # Check cancellation before starting
        if context.cancel_event.is_set():
            raise AnalysisCancelledError("analysis cancelled before execution")

        # Validate Trivy is available
        if not TrivyRunner.is_available(self._executable):
            raise ProviderError(
                f"Trivy is not installed or not available in PATH "
                f"(executable: {self._executable}). "
                "Install Trivy: https://trivy.dev/latest/getting-started/installation/",
                code="scanner_unavailable",
            )

        version = TrivyRunner.get_version(self._executable)
        logger.info(
            "Starting Trivy scan for %s (version=%s, run=%s)",
            context.full_name,
            version,
            context.run_id,
        )

        # Acquire repository source via GitHub
        workspace: WorkspaceHandle | None = None
        try:
            workspace = await self._acquire_repository(context)

            # Check cancellation after acquisition
            if context.cancel_event.is_set():
                raise AnalysisCancelledError("analysis cancelled after acquisition")

            # Execute Trivy on the cloned checkout
            repo_path = workspace.repo_path
            result = await self._runner.run_filesystem(
                repo_path,
                timeout_seconds=self._timeout_seconds,
            )

            # Check cancellation after scan
            if context.cancel_event.is_set():
                raise AnalysisCancelledError("analysis cancelled after scan")

            if not result.success:
                # Non-zero exit code from Trivy often means vulnerabilities were
                # found (exit code 1) or no scan targets were found (exit code 5).
                if result.exit_code == 1:
                    logger.info(
                        "Trivy found vulnerabilities (exit code 1, run=%s)",
                        context.run_id,
                    )
                elif result.exit_code == 5:
                    # No scan targets found — empty result, not a failure.
                    logger.info(
                        "Trivy found no scan targets (exit code 5, run=%s)",
                        context.run_id,
                    )
                    if self._findings_callback is not None:
                        await self._findings_callback([])
                    return
                else:
                    stderr_snippet = result.stderr[:500]
                    raise ProviderError(
                        f"Trivy scan failed (exit {result.exit_code}): {stderr_snippet}",
                        code="scanner_execution_failed",
                    )

            # Parse the output
            findings = self._parser.parse(
                result.stdout,
                analysis_run_id=context.run_id,
            )

            logger.info(
                "Trivy scan complete: %d findings for %s (run=%s)",
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
        """Acquire the repository checkout into a temporary workspace.

        Uses the user's GitHub access token via the token_resolver in the
        context to clone the repository.  The token is never logged or
        passed as a command-line argument.

        Raises:
            ProviderError: If acquisition fails.
        """
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
                branch=None,  # Use the default branch
            )

            # Check disk usage of the acquired workspace
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
    """Approximate directory size in megabytes.

    Walks the directory tree summing file sizes.  This is an estimate —
    it doesn't account for filesystem block alignment.
    """
    from pathlib import Path

    total = 0
    try:
        for entry in Path(path).rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except OSError:
        pass
    return total / (1024 * 1024)
