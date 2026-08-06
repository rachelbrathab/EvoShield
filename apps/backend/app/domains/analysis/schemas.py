"""Analysis domain API contracts.

`AnalysisRunRead` is the wire shape of one analysis run. `repository_full_name`
is populated from the ownership join so the UI can label runs without a second
request. No findings or vulnerabilities exist yet — those belong to Sprint 5
scanner contracts.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.analysis_run import AnalysisRunStatus


class AnalysisRunRead(BaseModel):
    """API contract for one analysis run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    # Filled by the router from the ownership join (not an ORM attribute).
    repository_full_name: str | None = None
    triggered_by: str
    status: AnalysisRunStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    analysis_version: str
    failure_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AnalysisRunListResponse(BaseModel):
    """Paginated list of analysis runs."""

    items: list[AnalysisRunRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class AnalysisRunCreateResponse(BaseModel):
    """Result of starting an analysis run."""

    run: AnalysisRunRead


class AnalysisRunCancelResponse(BaseModel):
    """Result of cancelling an analysis run."""

    run: AnalysisRunRead
