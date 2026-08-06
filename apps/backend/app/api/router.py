"""Aggregate router — the single mount point for all v1 sub-routers."""

from fastapi import APIRouter

from app.api.routers import analysis, auth, health, repositories

api_router = APIRouter()

api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# Analysis routes first: `/repositories/{id}/analysis` must never be shadowed
# by the repositories router's parameterized `/{repository_id}` paths.
api_router.include_router(analysis.repo_analysis_router, tags=["analysis"])
api_router.include_router(analysis.analysis_router, tags=["analysis"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
