"""System health endpoint — liveness plus dependency probes."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import get_settings
from app.domains.health.schemas import HealthResponse
from app.domains.health.service import check_database

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description="Reports service liveness and dependency connectivity.",
)
async def health() -> HealthResponse:
    settings = get_settings()
    database = await check_database()
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        database=database,
        timestamp=datetime.now(UTC),
    )
