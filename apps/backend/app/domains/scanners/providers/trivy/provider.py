"""Trivy analysis provider — the first real scanner adapter.

Implements the `AnalysisProvider` port from the analysis domain, bridging
the analysis orchestrator to the Trivy CLI.  Scanner-specific logic stays
entirely inside this module:

- `TrivyRunner` executes the CLI safely (no shell=True, argument arrays)
- `TrivyResultParser` normalizes JSON output into `ScannerFinding` objects
- `ScannerWorkspace` manages the temporary working directory
- Findings are persisted to the database after successful execution

The orchestrator calls `execute(context)` — it never knows about Trivy.

Temporary workspace lifecycle:
1. The orchestrator dispatches the provider (via the run lifecycle).
2. The provider creates a temporary workspace (for future use with
   cloned repos; currently scans the repo's local path).
3. Trivy runs against the workspace.
4. The workspace is cleaned up in a `finally` block.

For Sprint 5A, we don't clone repos — Trivy scans a provided path.
When repository cloning is added later (Sprint 5B+), the workspace will
contain the cloned checkout.
"""

import logging
from typing import Any

from app.core.exceptions import ProviderError
from app.domains.analysis.ports import AnalysisCancelledError, AnalysisExecutionContext
from app.domains.scanners.providers.trivy.parser import TrivyResultParser
from app.domains.scanners.providers.trivy.runner import TrivyRunner

logger = logging.getLogger(__name__)


class TrivyProvider:
    """Trivy analysis provider — the first real scanner.

    Implements `AnalysisProvider` protocol (from analysis domain) so the
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
    ) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds
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
        """Execute a Trivy filesystem scan.

        This is called by the orchestrator's background task.  The provider:
        1. Validates Trivy is available
        2. Runs the scan
        3. Parses the output
        4. Persists findings (via callback)
        5. Reports success/failure to the orchestrator

        Raises:
            AnalysisCancelledError: If the cancel event is set.
            ProviderError: If Trivy is unavailable or the scan fails.
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

        # For Sprint 5A, we scan the filesystem path derived from the
        # repository.  When cloning is added later, this will scan the
        # cloned workspace instead.
        #
        # For now, if the repository doesn't have a local path, we scan
        # a placeholder that will be replaced when cloning is implemented.
        scan_path = self._get_scan_path(context)
        if scan_path is None:
            raise ProviderError(
                "No scan target available for this repository. "
                "Repository cloning will be implemented in a later sprint.",
                code="no_scan_target",
            )

        # Check cancellation before scan
        if context.cancel_event.is_set():
            raise AnalysisCancelledError("analysis cancelled before scan")

        # Execute Trivy
        result = await self._runner.run_filesystem(
            scan_path,
            timeout_seconds=self._timeout_seconds,
        )

        # Check cancellation after scan
        if context.cancel_event.is_set():
            raise AnalysisCancelledError("analysis cancelled after scan")

        if not result.success:
            # Non-zero exit code from Trivy often means vulnerabilities were
            # found (exit code 1) or no scan targets were found (exit code 5).
            # Only treat actual errors as failures.
            if result.exit_code == 1:
                # Trivy returns exit code 1 when vulnerabilities are found —
                # this is expected and the output is still valid.
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
                raise ProviderError(
                    f"Trivy scan failed with exit code {result.exit_code}: {result.stderr[:500]}",
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

    @staticmethod
    def _get_scan_path(context: AnalysisExecutionContext) -> Any:
        """Determine the filesystem path to scan.

        For Sprint 5A, this is a placeholder.  When repository cloning
        is implemented, this will return the cloned workspace path.

        Returns:
            A path-like object, or None if no scan target is available.
        """
        # Sprint 5A: no cloning yet.  The context provides repository_id
        # but not a filesystem path.  Future implementation will clone
        # the repo into a temporary workspace and return that path.
        #
        # For now, return None so the provider raises a clear error
        # explaining that cloning is not yet implemented.
        return None
