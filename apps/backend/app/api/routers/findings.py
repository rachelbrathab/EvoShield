"""Findings endpoints — security scan results (Sprint 5A).

Every endpoint operates on `Finding` records only: list findings for an
analysis run or for a repository, with severity/type filtering and pagination.

All queries are ownership-scoped through the chain:
    finding → analysis_run → repository → owner

A user must never access findings belonging to another user.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.db.session import session_factory
from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.repository import FindingRepository
from app.models.user import User

router = APIRouter(prefix="/analysis", tags=["findings"])

UserDep = Annotated[User, Depends(get_current_user)]


def _finding_to_dict(finding) -> dict:
    """Convert a Finding ORM object to a response dict."""
    import json

    return {
        "id": str(finding.id),
        "analysis_run_id": str(finding.analysis_run_id),
        "scanner": finding.scanner,
        "scanner_version": finding.scanner_version,
        "finding_type": finding.finding_type.value,
        "severity": finding.severity.value,
        "title": finding.title,
        "description": finding.description,
        "package_name": finding.package_name,
        "installed_version": finding.installed_version,
        "fixed_version": finding.fixed_version,
        "vulnerability_id": finding.vulnerability_id,
        "references": json.loads(finding.references_json) if finding.references_json else [],
        "location": finding.location,
        "created_at": finding.created_at.isoformat() if finding.created_at else None,
    }


@router.get(
    "/{analysis_id}/findings",
    summary="List findings for an analysis run",
)
async def list_run_findings(
    user: UserDep,
    analysis_id: uuid.UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    severity: Annotated[Severity | None, Query()] = None,
    finding_type: Annotated[FindingType | None, Query()] = None,
) -> dict:
    """List findings for a specific analysis run, with optional filters.

    Ownership is enforced: the analysis run must belong to a repository
    owned by the authenticated user.
    """
    async with session_factory() as session:
        from app.domains.analysis.repository import AnalysisRunRepository

        runs_repo = AnalysisRunRepository(session)
        row = await runs_repo.get_for_owner(user.id, analysis_id)
        if row is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Analysis run not found.")

        findings_repo = FindingRepository(session)
        findings, total = await findings_repo.list_for_run(
            analysis_id,
            page=page,
            page_size=page_size,
            severity=severity,
            finding_type=finding_type,
        )

        total_pages = max(1, -(-total // page_size)) if total else 0
        return {
            "items": [_finding_to_dict(f) for f in findings],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }


@router.get(
    "/repositories/{repository_id}/findings",
    summary="List findings for all runs of a repository",
)
async def list_repository_findings(
    user: UserDep,
    repository_id: uuid.UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    severity: Annotated[Severity | None, Query()] = None,
    finding_type: Annotated[FindingType | None, Query()] = None,
) -> dict:
    """List findings for all analysis runs of a repository.

    Ownership is enforced through the repository owner.
    """
    async with session_factory() as session:
        findings_repo = FindingRepository(session)
        findings, total = await findings_repo.list_for_repository(
            user.id,
            repository_id,
            page=page,
            page_size=page_size,
            severity=severity,
            finding_type=finding_type,
        )

        total_pages = max(1, -(-total // page_size)) if total else 0
        return {
            "items": [_finding_to_dict(f) for f in findings],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
