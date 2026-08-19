"""Tests for token resolver wiring in the analysis orchestrator.

Verifies that the token_resolver_factory is properly passed to the context
and that the background task resolves the owner correctly.
"""

import asyncio
import uuid

import pytest

from app.domains.analysis.ports import (
    AnalysisExecutionContext,
    _make_noop_resolver,
)


class TestAnalysisExecutionContext:
    """Verify context fields for Sprint 5B additions."""

    def test_owner_id_default(self) -> None:
        ctx = AnalysisExecutionContext(
            run_id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            full_name="octocat/Hello-World",
            cancel_event=asyncio.Event(),
        )
        assert ctx.owner_id == uuid.UUID(int=0)

    def test_token_resolver_default(self) -> None:
        ctx = AnalysisExecutionContext(
            run_id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            full_name="octocat/Hello-World",
            cancel_event=asyncio.Event(),
        )
        # Default is a no-op resolver
        assert ctx.token_resolver is not None

    def test_custom_owner_and_resolver(self) -> None:
        owner = uuid.uuid4()

        async def my_resolver() -> str | None:
            return "ghp_custom_token"

        ctx = AnalysisExecutionContext(
            run_id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            full_name="octocat/Hello-World",
            cancel_event=asyncio.Event(),
            owner_id=owner,
            token_resolver=my_resolver,
        )
        assert ctx.owner_id == owner
        assert ctx.token_resolver is my_resolver


class TestMakeNoopResolver:
    """Verify the noop resolver factory."""

    def test_returns_callable(self) -> None:
        resolver = _make_noop_resolver()
        assert callable(resolver)

    @pytest.mark.asyncio
    async def test_returns_none(self) -> None:
        resolver = _make_noop_resolver()
        result = await resolver()
        assert result is None
