"""Analysis provider factory — the plug-in point for future scanners.

The orchestrator never constructs a provider; it receives one built here.
Selecting a scanner is a configuration change: set `ANALYSIS_PROVIDER=trivy`
once a Trivy adapter exists, and the whole pipeline runs through it. Unknown
provider names fail fast at startup/DI time instead of at run time.
"""

from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderError
from app.domains.analysis.ports import AnalysisProvider
from app.domains.analysis.providers.fake import FakeAnalysisProvider


def build_analysis_provider(settings: Settings | None = None) -> AnalysisProvider:
    """Return the provider selected by `settings.analysis_provider`."""
    settings = settings or get_settings()
    if settings.analysis_provider == "fake":
        return FakeAnalysisProvider(
            delay_seconds=settings.analysis_fake_delay_seconds,
            fail=settings.analysis_fake_fail,
        )
    raise ProviderError(
        f"Unknown analysis provider: {settings.analysis_provider!r}. "
        "Available: fake (scanner providers arrive in Sprint 5)."
    )
