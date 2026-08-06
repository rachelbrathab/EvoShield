"""GitHub domain API contracts (Sprint 3+).

The source-provider domain owns the repository contract. `RepositoryRead` is
the wire shape for connected repositories and is ready for the Sprint 3
list/detail endpoints — including the analysis-status fields introduced in
Sprint 3 preparation. No repository endpoints exist yet (Sprint 3).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.repository import AnalysisStatus


class RepositoryRead(BaseModel):
    """API contract for a tracked repository, including its analysis status."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    provider: str
    provider_repo_id: str | None = None
    name: str
    full_name: str
    default_branch: str | None = None
    html_url: str | None = None
    description: str | None = None
    is_private: bool = False
    is_active: bool = True

    # Analysis status — Sprint 4/5 pipelines transition this lifecycle state.
    analysis_status: AnalysisStatus
    last_analysis_at: datetime | None = None
    last_analysis_job_id: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None
