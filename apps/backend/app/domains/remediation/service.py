"""RemediationService — deterministic finding lifecycle and remediation intelligence.

Provides:
- Finding status management (OPEN → ACKNOWLEDGED → RESOLVED / FALSE_POSITIVE)
- Deterministic remediation guidance per finding type
- Fix availability assessment
- Remediation-aware prioritization
- Remediation summary metrics

All logic is deterministic and rule-based. No LLM, no ML, no prediction.
"""

import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.remediation.enums import FindingStatus, FixAvailability
from app.domains.remediation.guidance import (
    assess_fix_availability,
    get_remediation_guidance,
)
from app.domains.remediation.repository import (
    FindingStatusRepository,
    get_status_from_map,
)
from app.domains.remediation.schemas import (
    AnalysisRemediation,
    FindingRemediation,
    RemediationGuidance,
    RemediationStatusResponse,
    RemediationStatusUpdate,
    RemediationSummary,
)
from app.models.analysis_run import AnalysisRun
from app.models.finding import Finding
from app.models.finding_status import FindingStatusRecord
from app.models.repository import Repository


class RemediationService:
    """Deterministic remediation intelligence service."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._status_repo = FindingStatusRepository(session)

    async def get_remediation(
        self,
        owner_id: uuid.UUID,
        analysis_id: uuid.UUID,
    ) -> AnalysisRemediation:
        """Compute complete remediation intelligence for an analysis run."""
        run, repository = await self._load_analysis_with_owner(owner_id, analysis_id)
        findings = await self._load_findings(analysis_id)
        status_map = await self._status_repo.list_status_for_analysis(analysis_id)
        summary = await self._build_summary(findings, status_map)

        remediation_findings = self._build_findings(findings, status_map)

        return AnalysisRemediation(
            analysis_id=str(run.id),
            repository_id=str(repository.id),
            summary=summary,
            findings=remediation_findings,
        )

    async def update_status(
        self,
        owner_id: uuid.UUID,
        analysis_id: uuid.UUID,
        finding_id: uuid.UUID,
        update: RemediationStatusUpdate,
    ) -> RemediationStatusResponse:
        """Update the remediation status of a finding.

        Enforces owner scoping.
        """
        await self._load_analysis_with_owner(owner_id, analysis_id)

        # Validate the status value.
        try:
            new_status = FindingStatus(update.status)
        except ValueError:
            raise NotFoundError(
                f"Invalid status: {update.status}. "
                "Valid values: open, acknowledged, resolved, false_positive."
            ) from None

        # Verify the finding belongs to this analysis.
        finding = await self._load_finding_for_analysis(finding_id, analysis_id)

        record = await self._status_repo.set_status(
            finding.id,
            new_status,
            user_id=owner_id,
            note=update.note,
        )

        updated = record.updated_at
        if updated is not None:
            updated_str = updated.isoformat()
        else:
            updated_str = ""

        return RemediationStatusResponse(
            finding_id=str(finding.id),
            status=get_status_from_map({finding.id: record}, finding.id),
            updated_at=updated_str,
        )

    async def get_single_finding_remediation(
        self,
        owner_id: uuid.UUID,
        analysis_id: uuid.UUID,
        finding_id: uuid.UUID,
    ) -> FindingRemediation:
        """Get remediation details for a single finding."""
        await self._load_analysis_with_owner(owner_id, analysis_id)
        finding = await self._load_finding_for_analysis(finding_id, analysis_id)
        status_record = await self._status_repo.get_for_owner(owner_id, finding_id)
        status_value = (
            get_status_from_map({finding_id: status_record}, finding_id)
            if status_record is not None
            else FindingStatus.OPEN.value
        )

        return self._build_single_finding(finding, status_value)

    # ── Data loading ────────────────────────────────────────────────────

    async def _load_analysis_with_owner(
        self, owner_id: uuid.UUID, analysis_id: uuid.UUID
    ) -> tuple[AnalysisRun, Repository]:
        from sqlalchemy import select

        stmt = (
            select(AnalysisRun, Repository)
            .join(Repository, AnalysisRun.repository_id == Repository.id)
            .where(
                AnalysisRun.id == analysis_id,
                Repository.owner_id == owner_id,
            )
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            raise NotFoundError("Analysis run not found.")
        return row[0], row[1]

    async def _load_findings(self, analysis_id: uuid.UUID) -> list[Finding]:
        from sqlalchemy import select

        stmt = (
            select(Finding)
            .where(Finding.analysis_run_id == analysis_id)
            .order_by(Finding.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def _load_finding_for_analysis(
        self, finding_id: uuid.UUID, analysis_id: uuid.UUID
    ) -> Finding:
        from sqlalchemy import select

        stmt = select(Finding).where(
            Finding.id == finding_id,
            Finding.analysis_run_id == analysis_id,
        )
        finding = (await self._session.execute(stmt)).scalar_one_or_none()
        if finding is None:
            raise NotFoundError("Finding not found.")
        return finding

    # ── Building responses ──────────────────────────────────────────────

    def _build_findings(
        self,
        findings: list[Finding],
        status_map: Mapping[uuid.UUID, FindingStatusRecord],
    ) -> list[FindingRemediation]:
        """Build remediation info for all findings, sorted by priority."""
        result: list[FindingRemediation] = []
        for f in findings:
            status_value = get_status_from_map(status_map, f.id)
            result.append(self._build_single_finding(f, status_value))

        # Sort by priority (lower = more urgent).
        result.sort(key=lambda x: x.priority)
        return result

    def _build_single_finding(self, finding: Finding, status_value: str) -> FindingRemediation:
        """Build remediation info for a single finding."""
        ftype = _enum_val(finding.finding_type)
        severity = _enum_val(finding.severity)

        fix_avail = assess_fix_availability(
            finding_type=ftype,
            fixed_version=finding.fixed_version,
            vulnerability_id=finding.vulnerability_id,
            installed_version=finding.installed_version,
        )

        guidance_dict = get_remediation_guidance(
            finding_type=ftype,
            scanner=finding.scanner,
            title=finding.title,
            description=finding.description,
            package_name=finding.package_name,
            installed_version=finding.installed_version,
            fixed_version=finding.fixed_version,
            vulnerability_id=finding.vulnerability_id,
            location=finding.location,
        )

        priority = _compute_priority(
            severity=severity,
            finding_type=ftype,
            fix_availability=fix_avail.value,
            status=status_value,
        )

        return FindingRemediation(
            finding_id=str(finding.id),
            severity=severity,
            finding_type=ftype,
            scanner=finding.scanner,
            title=finding.title,
            status=status_value,
            priority=priority,
            fix_availability=fix_avail.value,
            package_name=finding.package_name,
            installed_version=finding.installed_version,
            fixed_version=finding.fixed_version,
            vulnerability_id=finding.vulnerability_id,
            location=finding.location,
            guidance=RemediationGuidance(**guidance_dict),
        )

    async def _build_summary(
        self,
        findings: list[Finding],
        status_map: Mapping[uuid.UUID, FindingStatusRecord],
    ) -> RemediationSummary:
        """Build aggregated remediation metrics."""
        total = len(findings)
        counts: dict[str, int] = {s.value: 0 for s in FindingStatus}
        fixable = 0
        unfixable = 0
        critical_open = 0
        high_open = 0

        for f in findings:
            status_value = get_status_from_map(status_map, f.id)
            counts[status_value] = counts.get(status_value, 0) + 1

            fix_avail = assess_fix_availability(
                finding_type=_enum_val(f.finding_type),
                fixed_version=f.fixed_version,
                vulnerability_id=f.vulnerability_id,
                installed_version=f.installed_version,
            )
            if fix_avail == FixAvailability.FIX_AVAILABLE:
                fixable += 1
            elif fix_avail in (FixAvailability.NO_KNOWN_FIX, FixAvailability.UNKNOWN):
                unfixable += 1

            # Count open critical/high for prioritization.
            if status_value == FindingStatus.OPEN.value:
                sev = _enum_val(f.severity)
                if sev == "critical":
                    critical_open += 1
                elif sev == "high":
                    high_open += 1

        resolved_or_fp = counts.get(FindingStatus.RESOLVED.value, 0) + counts.get(
            FindingStatus.FALSE_POSITIVE.value, 0
        )
        rate = (resolved_or_fp / total * 100.0) if total > 0 else 0.0

        return RemediationSummary(
            total_findings=total,
            open_count=counts.get(FindingStatus.OPEN.value, 0),
            acknowledged_count=counts.get(FindingStatus.ACKNOWLEDGED.value, 0),
            resolved_count=counts.get(FindingStatus.RESOLVED.value, 0),
            false_positive_count=counts.get(FindingStatus.FALSE_POSITIVE.value, 0),
            fixable_count=fixable,
            unfixable_count=unfixable,
            remediation_rate=round(rate, 1),
            critical_open=critical_open,
            high_open=high_open,
        )


# ── Helpers ──────────────────────────────────────────────────────────────


def _enum_val(obj: object) -> str:
    """Extract the string value from an enum or return str(obj)."""
    val = getattr(obj, "value", None)
    if val is not None:
        return str(val)
    return str(obj)


_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
_TYPE_ORDER = {
    "secret": 0,
    "vulnerability": 1,
    "sast": 2,
    "configuration": 3,
    "license": 4,
    "sbom": 5,
}
_FIX_ORDER = {
    FixAvailability.FIX_AVAILABLE.value: 0,
    FixAvailability.NO_KNOWN_FIX.value: 1,
    FixAvailability.UNKNOWN.value: 2,
    FixAvailability.NOT_APPLICABLE.value: 3,
}
_STATUS_ORDER = {
    FindingStatus.OPEN.value: 0,
    FindingStatus.ACKNOWLEDGED.value: 1,
    FindingStatus.RESOLVED.value: 2,
    FindingStatus.FALSE_POSITIVE.value: 3,
}


def _compute_priority(
    *,
    severity: str,
    finding_type: str,
    fix_availability: str,
    status: str,
) -> int:
    """Compute a deterministic remediation priority score.

    Lower number = higher priority. Considered factors:
    1. Status (OPEN > ACKNOWLEDGED > RESOLVED > FALSE_POSITIVE)
    2. Severity (critical > high > medium > low > unknown)
    3. Fix availability (fix available > no fix > unknown > not applicable)
    4. Finding type (secret > vulnerability > sast > configuration > license)

    Returns a composite score.
    """
    status_p = _STATUS_ORDER.get(status, 0)
    sev_p = _SEVERITY_ORDER.get(severity, 4)
    fix_p = _FIX_ORDER.get(fix_availability, 2)
    type_p = _TYPE_ORDER.get(finding_type, 5)

    # Weighted composite: status dominates, then severity, fix, type.
    return status_p * 1000 + sev_p * 100 + fix_p * 10 + type_p
