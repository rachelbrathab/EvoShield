"""Intelligence endpoints — repository security intelligence (Sprint 6).

Provides a single owner-scoped endpoint that computes and returns
repository intelligence for a completed analysis run.

All queries are ownership-scoped through the chain:
    intelligence → analysis_run → repository → owner
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import session_factory
from app.domains.intelligence.service import IntelligenceService
from app.models.user import User

router = APIRouter(prefix="/analysis", tags=["intelligence"])

UserDep = Annotated[User, Depends(get_current_user)]


@router.get(
    "/{analysis_id}/intelligence",
    summary="Get repository intelligence for an analysis run",
)
async def get_analysis_intelligence(
    user: UserDep,
    analysis_id: uuid.UUID,
) -> dict:
    """Compute and return repository intelligence for a specific analysis run.

    The intelligence includes:
    - Risk score and level
    - Finding aggregation (by severity, type, scanner)
    - Risk factors with explanations
    - Prioritized top findings
    - Trend comparison with previous analysis
    - Scanner coverage

    Ownership is enforced: the analysis run must belong to a repository
    owned by the authenticated user.
    """
    async with session_factory() as session:
        service = IntelligenceService(session)
        intelligence = await service.get_intelligence(user.id, analysis_id)
        return intelligence.model_dump()
