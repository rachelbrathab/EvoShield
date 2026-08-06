"""Aggregate router — the single mount point for all v1 sub-routers."""

from fastapi import APIRouter

from app.api.routers import auth, health

api_router = APIRouter()

# Health/liveness probes. New resources mount here as sprints land:
#   api_router.include_router(repositories.router, prefix="/repositories", …)
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
