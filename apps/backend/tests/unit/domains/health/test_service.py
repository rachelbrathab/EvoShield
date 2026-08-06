"""Unit tests for the health domain service.

The service depends on the `DatabaseProbe` port (see
`app/domains/health/ports.py`), so these tests inject a lightweight fake and
never touch a real database — the DB-backed behaviour is covered by the
integration tests in `tests/integration/`.
"""

import pytest

from app.domains.health.ports import DatabaseProbe
from app.domains.health.service import check_database


class _FakeConnection:
    """Duck-typed async connection: answers or fails, never touches SQLAlchemy."""

    def __init__(self, *, ok: bool) -> None:
        self.ok = ok

    async def __aenter__(self) -> "_FakeConnection":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def execute(self, *args: object, **kwargs: object) -> object:
        if not self.ok:
            raise RuntimeError("connection refused")
        return object()


class _FakeEngine:
    """A `DatabaseProbe` fake that yields a scripted connection."""

    def __init__(self, *, ok: bool) -> None:
        self.ok = ok

    def connect(self) -> _FakeConnection:
        return _FakeConnection(ok=self.ok)


def _make_probe(*, ok: bool) -> DatabaseProbe:
    return _FakeEngine(ok=ok)


async def test_check_database_returns_ok_when_db_answers() -> None:
    assert await check_database(probe=_make_probe(ok=True)) == "ok"


async def test_check_database_returns_unavailable_when_db_fails() -> None:
    assert await check_database(probe=_make_probe(ok=False)) == "unavailable"


@pytest.mark.parametrize("ok", [True, False])
async def test_check_database_never_raises(ok: bool) -> None:
    result = await check_database(probe=_make_probe(ok=ok))
    assert result in {"ok", "unavailable"}
