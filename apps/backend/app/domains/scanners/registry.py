"""Scanner registry — the plug-in point for scanner providers.

Replaces the single-provider ``factory.py`` with a registry that can
return multiple providers.  Each scanner registers itself by name; the
orchestrator queries the registry to determine which scanners to execute.

Sprint 5C.1 ships only ``trivy``.  Future scanners register themselves
here without modifying the orchestrator.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core.exceptions import ProviderError

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.domains.analysis.ports import AnalysisProvider

logger = logging.getLogger(__name__)

# Type alias for the factory callable that builds a provider from settings.
BuilderFactory = Callable[["Settings"], "AnalysisProvider"]


def _build_trivy(settings: Settings) -> AnalysisProvider:
    from app.domains.scanners.providers.trivy.provider import TrivyProvider

    return TrivyProvider(
        executable=settings.trivy_executable,
        timeout_seconds=settings.trivy_timeout_seconds,
    )


def _build_gitleaks(settings: Settings) -> AnalysisProvider:
    from app.domains.scanners.providers.gitleaks.provider import GitleaksProvider

    return GitleaksProvider(
        executable=settings.gitleaks_executable,
        timeout_seconds=settings.gitleaks_timeout_seconds,
    )


# Registry: scanner_name → factory function
_REGISTRY: dict[str, BuilderFactory] = {
    "trivy": _build_trivy,
    "gitleaks": _build_gitleaks,
}


def get_registered_scanners() -> list[str]:
    """Return the names of all registered scanners."""
    return list(_REGISTRY.keys())


def build_scanner(name: str, settings: Settings) -> AnalysisProvider:
    """Build a scanner provider by name.

    Raises:
        ProviderError: If the scanner name is not registered.
    """
    factory = _REGISTRY.get(name)
    if factory is None:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ProviderError(
            f"Unknown scanner: {name!r}. Available: {available}.",
            code="unknown_scanner",
        )
    return factory(settings)


def parse_scanner_list(scanners_str: str) -> list[str]:
    """Parse a comma-separated scanner configuration string.

    Returns a deduplicated, order-preserving list of scanner names.
    Raises ProviderError on empty input.
    """
    names = [s.strip().lower() for s in scanners_str.split(",") if s.strip()]
    if not names:
        raise ProviderError(
            "No scanners configured. Set ANALYSIS_SCANNERS to a comma-separated list.",
            code="no_scanners_configured",
        )
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique
