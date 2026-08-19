"""Trivy scanner adapter.

The first real scanner integrated into EvoShield.  Implements the
`AnalysisProvider` protocol so the orchestrator can dispatch it as
a drop-in replacement for the fake provider.

Usage:
    Set `ANALYSIS_PROVIDER=trivy` in the environment.
    Trivy must be installed and available in PATH.
"""

from app.domains.scanners.providers.trivy.parser import TrivyResultParser
from app.domains.scanners.providers.trivy.provider import TrivyProvider
from app.domains.scanners.providers.trivy.runner import TrivyRunner

__all__ = [
    "TrivyProvider",
    "TrivyResultParser",
    "TrivyRunner",
]
