"""Analysis domain — the orchestration layer every future scanner plugs into.

Sprint 4A ships the *infrastructure* only: the run state machine
(`AnalysisOrchestrator`), the `AnalysisProvider` port, the simulation
provider, and the run aggregate. Real scanners arrive in Sprint 5 as new
providers selected via `factory.py`.
"""

from app.domains.analysis.factory import build_analysis_provider
from app.domains.analysis.orchestrator import AnalysisOrchestrator
from app.domains.analysis.ports import (
    AnalysisCancelledError,
    AnalysisExecutionContext,
    AnalysisProvider,
)
from app.domains.analysis.providers import FakeAnalysisProvider

__all__ = [
    "AnalysisCancelledError",
    "AnalysisExecutionContext",
    "AnalysisOrchestrator",
    "AnalysisProvider",
    "FakeAnalysisProvider",
    "build_analysis_provider",
]
