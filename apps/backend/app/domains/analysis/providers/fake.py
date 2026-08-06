"""Fake analysis provider — validates the orchestration layer only.

Sprint 4A deliberately performs *no* security scanning. `FakeAnalysisProvider`
implements the `AnalysisProvider` port and simulates a provider run: it sleeps
for a configurable duration (honoring cancellation), then succeeds — or fails
when configured. It is the default provider (`ANALYSIS_PROVIDER=fake`) until
real scanners (Trivy, Syft, Grype, Semgrep, Gitleaks) land in Sprint 5 as
sibling adapters selected via `factory.py`.
"""

import asyncio
from collections.abc import Awaitable, Callable

from app.core.exceptions import ProviderError
from app.domains.analysis.ports import AnalysisCancelledError, AnalysisExecutionContext


class FakeAnalysisProvider:
    """Simulated provider with configurable delay and failure behavior."""

    name = "fake"
    version = "0.1.0"

    def __init__(
        self,
        *,
        delay_seconds: float = 4.0,
        fail: bool = False,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        # `sleep` is injectable so tests can use a real (fast) asyncio.sleep
        # or a stub; the default is asyncio.sleep.
        self._delay_seconds = max(0.0, delay_seconds)
        self._fail = fail
        self._sleep = sleep or asyncio.sleep

    def supports(self, repository) -> bool:
        return True

    async def execute(self, context: AnalysisExecutionContext) -> None:
        # Poll the cancel event in small steps so a cancellation aborts the
        # simulated run promptly instead of waiting out the full delay.
        step = 0.05
        remaining = self._delay_seconds
        while remaining > 0:
            if context.cancel_event.is_set():
                raise AnalysisCancelledError("analysis cancelled during execution")
            await self._sleep(min(step, remaining))
            remaining -= step
        if context.cancel_event.is_set():
            raise AnalysisCancelledError("analysis cancelled during execution")
        if self._fail:
            raise ProviderError("Fake provider failed on purpose (ANALYSIS_FAKE_FAIL=1).")
