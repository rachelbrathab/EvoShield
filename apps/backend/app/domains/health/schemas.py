"""Health domain API contract."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Payload returned by GET /api/v1/health."""

    status: str = Field(description="Overall service status ('ok' | 'degraded')")
    version: str = Field(description="Backend version")
    environment: str = Field(description="Runtime environment name")
    database: str = Field(description="Database connectivity ('ok' | 'unavailable')")
    timestamp: datetime = Field(description="Response time (UTC)")
