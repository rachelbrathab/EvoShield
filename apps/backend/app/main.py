"""EvoShield API application factory.

Clean-architecture boundary: this module owns *composition* (wiring) only.
Business logic lives in `domains`, data access in `repositories`, and the
HTTP surface in `api/routers`.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.security import apply_security_middleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks.

    Startup runs the stranded-run reaper (Sprint 8): in-process background
    tasks die with the process, so any run still ``queued``/``running`` after
    a restart is orphaned forever — blocking re-starts via the DB-level
    single-active-run guard. Marking them failed keeps the repository
    lifecycle honest and re-startable. See app/domains/analysis/reaper.py.
    """
    from app.db.session import session_factory
    from app.domains.analysis.reaper import recover_stranded_runs

    recovered = 0
    try:
        async with session_factory() as session:
            recovered = len(await recover_stranded_runs(session))
    except Exception:
        # Recovery must never prevent the API from serving.
        logger.exception("Stranded-run recovery failed at startup")
    else:
        if recovered:
            logger.warning("Recovered %d stranded analysis run(s) at startup", recovered)

    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend API for EvoShield — unified repository security intelligence and remediation."
        ),
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Order matters: Starlette wraps the earliest-added middleware outermost.
    # Host validation must run before CORS, so security first, then CORS.
    apply_security_middleware(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "docs": "/docs"}

    logger.info(
        "Application started: %s v%s (%s)",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )
    return app


app = create_app()
