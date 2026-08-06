"""Analysis domain ports — the seam future scanners implement.

The orchestrator depends only on `AnalysisProvider`; it has no idea what a
Trivy, Syft, Grype, Semgrep or Gitleaks run involves. Each future scanner
ships as an adapter implementing this port (name/version/supports/execute)
and is selected in `factory.py` — the orchestrator, repository and API do not
change (see docs/adr/0008-analysis-domain.md).

`AnalysisCancelledError` is the domain's internal control-flow signal: a
provider raises it (or the orchestrator observes the cancel event) when a run
is cancelled mid-execution, and the orchestrator aborts without overwriting
the CANCELLED state.
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Protocol

from app.models.repository import Repository


class AnalysisCancelledError(Exception):
    """Raised by a provider when its execution was cancelled mid-run."""


@dataclass(frozen=True)
class AnalysisExecutionContext:
    """Everything a provider needs to run one analysis.

    `cancel_event` is set by the orchestrator when the run is cancelled; a
    cooperative provider polls it between work chunks and raises
    `AnalysisCancelledError` (or just returns) so the run aborts promptly.
    """

    run_id: uuid.UUID
    repository_id: uuid.UUID
    # Human-facing identity of the repository being analyzed, e.g.
    # "octocat/Hello-World". Providers may use it for labels/logs.
    full_name: str
    cancel_event: asyncio.Event


class AnalysisProvider(Protocol):
    """Port every analysis provider (scanner pipeline) implements."""

    #: Stable provider name, e.g. "trivy" — used in run metadata and logs.
    name: str
    #: Provider version, surfaced on the run record (`analysis_version`).
    version: str

    def supports(self, repository: Repository) -> bool:
        """Whether this provider can analyze the given repository.

        A structure-analysis provider might require a checked-out repository
        later; a Trivy provider may skip archived repositories. Defaults to
        True for every provider unless overridden.
        """
        return True

    async def execute(self, context: AnalysisExecutionContext) -> None:
        """Run the analysis.

        Must observe `context.cancel_event` (raising `AnalysisCancelledError`)
        and raise on failure. Return normally on success; findings are
        reported elsewhere (Sprint 5) — this run only tracks lifecycle.
        """
        ...
