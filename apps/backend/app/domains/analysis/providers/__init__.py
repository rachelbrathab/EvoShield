"""Analysis provider adapters.

Each module in this package implements the `AnalysisProvider` port
(`domains/analysis/ports.py`). Only the simulation provider ships today;
scanner providers join in Sprint 5 without touching the orchestrator.
"""

from app.domains.analysis.providers.fake import FakeAnalysisProvider

__all__ = ["FakeAnalysisProvider"]
