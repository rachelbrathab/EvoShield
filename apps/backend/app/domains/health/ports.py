"""Health domain ports — the interfaces this domain depends on.

Following the "ports before tools" rule, the health domain depends on a
minimal structural interface instead of a concrete engine. The application's
SQLAlchemy engine satisfies `DatabaseProbe` structurally, and tests provide
lightweight fakes — so the domain never imports a driver-specific type.
"""

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol


class ConnectionProbe(Protocol):
    """An open async connection that can execute a probe statement."""

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any: ...


class DatabaseProbe(Protocol):
    """Anything that can open an async connection usable for a probe query."""

    def connect(self) -> AbstractAsyncContextManager[ConnectionProbe]: ...
