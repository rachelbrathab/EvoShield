"""Remediation endpoints — finding lifecycle and remediation intelligence.

Provides owner-scoped endpoints for:
- Viewing remediation guidance for all findings in an analysis
- Viewing remediation details for a single finding
- Updating a finding's remediation status

All queries are ownership-scoped through the chain:
    remediation → analysis_run → repository → owner
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import session_factory
from app.domains.remediation.schemas import RemediationStatusUpdate
from app.domains.remediation.service import RemediationService
from app.models.user import User

router = APIRouter(prefix="/analysis", tags=["remediation"])

UserDep = Annotated[User, Depends(get_current_user)]


@router.get(
    "/{analysis_id}/remediation",
    summary="Get remediation intelligence for an analysis run",
)
async def get_analysis_remediation(
    user: UserDep,
    analysis_id: uuid.UUID,
) -> dict:
    """Compute and return remediation intelligence for a specific analysis run.

    Includes:
    - Remediation summary (open/acknowledged/resolved/false_positive counts)
    - Per-finding remediation guidance
    - Fix availability
    - Priority ordering

    Ownership is enforced.
    """
    async with session_factory() as session:
        service = RemediationService(session)
        remediation = await service.get_remediation(user.id, analysis_id)
        return remediation.model_dump()


@router.get(
    "/{analysis_id}/findings/{finding_id}/remediation",
    summary="Get remediation details for a single finding",
)
async def get_finding_remediation(
    user: UserDep,
    analysis_id: uuid.UUID,
    finding_id: uuid.UUID,
) -> dict:
    """Return remediation guidance for a single finding.

    Ownership is enforced through the analysis run.
    """
    async with session_factory() as session:
        service = RemediationService(session)
        result = await service.get_single_finding_remediation(user.id, analysis_id, finding_id)
        return result.model_dump()


@router.patch(
    "/{analysis_id}/findings/{finding_id}/status",
    summary="Update a finding's remediation status",
)
async def update_finding_status(
    user: UserDep,
    analysis_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: RemediationStatusUpdate,
) -> dict:
    """Update the remediation status of a finding.

    Valid statuses: open, acknowledged, resolved, false_positive.

    Ownership is enforced. Only the repository owner may change status.
    """
    async with session_factory() as session:
        service = RemediationService(session)
        result = await service.update_status(user.id, analysis_id, finding_id, body)
        await session.commit()
        return result.model_dump()
