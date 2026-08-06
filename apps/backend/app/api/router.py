"""Aggregate router — the single mount point for all v1 sub-routers."""

from fastapi import APIRouter

from app.api.routers import auth, health, repositories

api_router = APIRouter()

api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
