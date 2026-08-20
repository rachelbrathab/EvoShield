"""Grype analysis provider — SBOM-based vulnerability scanner adapter.

Implements the ``AnalysisProvider`` port from the analysis domain, bridging
the analysis orchestrator to the Syft + Grype pipeline:

1. ``GitHubRepositorySource`` acquires the repository checkout
2. ``GrypeRunner`` executes Syft (SBOM) → Grype (vulnerability matching)
3. ``GrypeResultParser`` normalizes Grype JSON output into ``ScannerFinding``
   objects with **mandatory output redaction**

The orchestrator calls ``execute(context)`` — it never knows about Syft or
Grype internally.

SECURITY: Raw SBOM content and Grype scanner output are never persisted
or exposed through the API. Only normalized finding metadata is retained.
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
from app.domains.scanners.providers.grype.parser import GrypeResultParser
from app.domains.scanners.providers.grype.runner import GrypeRunner

logger = logging.getLogger(__name__)


class GrypeProvider:
    """Grype SBOM-based vulnerability provider.

    Implements ``AnalysisProvider`` protocol so the orchestrator can dispatch
    it as a drop-in scanner alongside Trivy, Gitleaks, and Semgrep.
    """

    name = "grype"
    version = "0.1.0"

    def __init__(
        self,
        *,
        syft_executable: str = "syft",
        grype_executable: str = "grype",
        syft_timeout_seconds: float = 120.0,
        grype_timeout_seconds: float = 120.0,
        findings_callback: Any = None,
        git_executable: str = "git",
        max_repository_size_mb: float = 500.0,
        repository_clone_timeout_seconds: float = 120.0,
    ) -> None:
        self._syft_executable = syft_executable
        self._grype_executable = grype_executable
        self._syft_timeout = syft_timeout_seconds
        self._grype_timeout = grype_timeout_seconds
        self._git_executable = git_executable
        self._max_repository_size_mb = max_repository_size_mb
        self._repository_clone_timeout_seconds = repository_clone_timeout_seconds
        self._runner = GrypeRunner(
            syft_executable=syft_executable,
            grype_executable=grype_executable,
            syft_timeout_seconds=syft_timeout_seconds,
            grype_timeout_seconds=grype_timeout_seconds,
        )
        self._parser = GrypeResultParser(
            scanner_name=self.name,
            scanner_version=self.version,
        )
        # Callback invoked after successful scan to persist findings.
        self._findings_callback = findings_callback

    def supports(self, repository: Any) -> bool:
        """Grype can scan any non-archived, non-disabled repository."""
        if hasattr(repository, "archived") and repository.archived:
            return False
        if hasattr(repository, "disabled") and repository.disabled:
            return False
        return True

    async def execute(self, context: AnalysisExecutionContext) -> None:
        """Execute a Grype vulnerability scan with repository acquisition.

        Pipeline:
        1. Validate Syft and Grype are available
        2. Acquire repository via GitHub API
        3. Generate SBOM with Syft
        4. Match vulnerabilities with Grype
        5. Parse JSON output
        6. Normalize findings
        7. Persist findings
        8. Clean up workspace + SBOM

        Raises:
            AnalysisCancelledError: If the cancel event is set.
            ProviderError: If any step fails.
        """
        if context.cancel_event.is_set():
            raise AnalysisCancelledError("analysis cancelled before execution")

        # Validate both tools are available
        if not GrypeRunner.is_available(self._syft_executable):
            raise ProviderError(
                f"Syft is not installed or not available in PATH "
                f"(executable: {self._syft_executable}). "
                "Install Syft: https://github.com/anchore/syft",
                code="scanner_unavailable",
            )
        if not GrypeRunner.is_available(self._grype_executable):
            raise ProviderError(
                f"Grype is not installed or not available in PATH "
                f"(executable: {self._grype_executable}). "
                "Install Grype: https://github.com/anchore/grype",
                code="scanner_unavailable",
            )

        syft_version = GrypeRunner.get_version(self._syft_executable)
        grype_version = GrypeRunner.get_version(self._grype_executable)
        logger.info(
            "Starting Grype scan for %s (syft=%s, grype=%s, run=%s)",
            context.full_name,
            syft_version,
            grype_version,
            context.run_id,
        )

        # Acquire repository source via GitHub
        workspace: WorkspaceHandle | None = None
        try:
            workspace = await self._acquire_repository(context)

            if context.cancel_event.is_set():
                raise AnalysisCancelledError("analysis cancelled after acquisition")

            # Execute Syft → Grype pipeline on the cloned checkout
            repo_path = workspace.repo_path
            result = await self._runner.run_pipeline(
                repo_path,
                syft_timeout=self._syft_timeout,
                grype_timeout=self._grype_timeout,
            )

            if context.cancel_event.is_set():
                raise AnalysisCancelledError("analysis cancelled after scan")

            if not result.success:
                # SECURITY: Never include raw stderr — it may contain
                # dependency details or sensitive repository information.
                raise ProviderError(
                    f"Grype scan failed with exit code {result.exit_code}.",
                    code="scanner_execution_failed",
                )

            # Parse the output — only safe metadata is retained.
            findings = self._parser.parse(
                result.stdout,
                analysis_run_id=context.run_id,
            )

            logger.info(
                "Grype scan complete: %d vulnerability findings for %s (run=%s)",
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
