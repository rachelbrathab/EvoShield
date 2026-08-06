"""Health domain business logic — probe external dependencies."""

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import engine as default_engine
from app.domains.health.ports import DatabaseProbe

logger = get_logger(__name__)


async def check_database(probe: DatabaseProbe | None = None) -> str:
    """Return ``'ok'`` when the database answers a trivial query, else ``'unavailable'``.

    ``probe`` is injectable for unit tests; it defaults to the application's
    shared engine (see ``app/db/session.py``).
    """
    target: DatabaseProbe = probe if probe is not None else default_engine
    try:
        async with target.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # a probe must never raise
        logger.warning("Database connectivity check failed: %s", exc)
        return "unavailable"
