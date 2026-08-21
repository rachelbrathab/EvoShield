"""Intelligence service — computes repository intelligence from scanner evidence.

All computation is deterministic, bounded, and testable.
No external services, no LLM, no machine learning.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.intelligence.schemas import (
    FindingTypeCounts,
    PriorityFinding,
    RemediationMetrics,
    RepositoryIntelligence,
    RiskFactor,
    ScannerCounts,
    ScannerCoverage,
    ScannerDetail,
    SeverityCounts,
    TrendInfo,
)
from app.domains.intelligence.scoring import (
    aggregate_by_scanner,
    aggregate_by_type,
    aggregate_severities,
    compute_risk_level,
    compute_risk_score,
    count_secrets,
    count_unfixed_vulns,
)
from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.scanner_run import ScannerRun


class IntelligenceService:
    """Computes repository intelligence from existing scanner data."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_intelligence(
        self,
        owner_id: uuid.UUID,
        analysis_id: uuid.UUID,
    ) -> RepositoryIntelligence:
        """Compute complete repository intelligence for an analysis run."""
        run, repository = await self._load_analysis_with_owner(owner_id, analysis_id)
        findings = await self._load_findings(analysis_id)
        scanner_runs = await self._load_scanner_runs(analysis_id)
        previous_run = await self._find_previous_completed(repository.id, analysis_id)
        previous_findings: list[Finding] = []
        if previous_run is not None:
            previous_findings = await self._load_findings(previous_run.id)

        sev_raw = aggregate_severities(findings)
        type_raw = aggregate_by_type(findings)
        scanner_raw = aggregate_by_scanner(findings)

        severity_counts = self._build_severity_counts(sev_raw)
        finding_type_counts = self._build_finding_type_counts(type_raw)
        scanner_counts = self._build_scanner_counts(scanner_raw)

        secret_count = count_secrets(findings)
        unfixed_count = count_unfixed_vulns(findings)
        risk_score = compute_risk_score(
            severity_counts=sev_raw,
            secret_count=secret_count,
            unfixed_vuln_count=unfixed_count,
        )
        risk_level = compute_risk_level(risk_score)

        risk_factors = self._generate_risk_factors(findings, sev_raw, secret_count, unfixed_count)
        top_findings = self._prioritize_findings(findings, limit=10)
        trend = self._compute_trend(findings, previous_findings, previous_run)
        coverage = self._compute_scanner_coverage(scanner_runs)
        summary = self._generate_summary(risk_level, len(findings), sev_raw, coverage)
        remediation = await self._compute_remediation_metrics(findings, analysis_id)

        return RepositoryIntelligence(
            repository_id=str(repository.id),
            analysis_id=str(run.id),
            generated_at=datetime.now(UTC).isoformat(),
            risk_score=risk_score,
            risk_level=risk_level,
            analysis_status=run.status.value,
            total_findings=len(findings),
            severity_counts=severity_counts,
            finding_type_counts=finding_type_counts,
            scanner_counts=scanner_counts,
            risk_factors=risk_factors,
            top_findings=top_findings,
            remediation_metrics=remediation,
            trend=trend,
            scanner_coverage=coverage,
            summary=summary,
        )

    # ── Remediation metrics ─────────────────────────────────────────────

    async def _compute_remediation_metrics(
        self, findings: list[Finding], analysis_id: uuid.UUID
    ) -> RemediationMetrics:
        """Compute remediation metrics from finding statuses."""
        from app.domains.remediation.enums import FindingStatus, FixAvailability
        from app.domains.remediation.guidance import assess_fix_availability
        from app.domains.remediation.repository import FindingStatusRepository

        status_repo = FindingStatusRepository(self._session)
        status_map = await status_repo.list_status_for_analysis(analysis_id)

        open_count = 0
        acknowledged_count = 0
        resolved_count = 0
        fp_count = 0
        fixable_count = 0

        for f in findings:
            status_record = status_map.get(f.id)
            status_val = (
                status_record.status.value  # type: ignore[union-attr]
                if status_record is not None
                else FindingStatus.OPEN.value
            )
            if status_val == FindingStatus.OPEN.value:
                open_count += 1
            elif status_val == FindingStatus.ACKNOWLEDGED.value:
                acknowledged_count += 1
            elif status_val == FindingStatus.RESOLVED.value:
                resolved_count += 1
            elif status_val == FindingStatus.FALSE_POSITIVE.value:
                fp_count += 1

            fix = assess_fix_availability(
                finding_type=_enum_val(f.finding_type),
                fixed_version=f.fixed_version,
                vulnerability_id=f.vulnerability_id,
                installed_version=f.installed_version,
            )
            if fix == FixAvailability.FIX_AVAILABLE:
                fixable_count += 1

        total = len(findings)
        resolved_or_fp = resolved_count + fp_count
        rate = (resolved_or_fp / total * 100.0) if total > 0 else 0.0

        return RemediationMetrics(
            open_count=open_count,
            acknowledged_count=acknowledged_count,
            resolved_count=resolved_count,
            false_positive_count=fp_count,
            fixable_count=fixable_count,
            remediation_rate=round(rate, 1),
        )

    # ── Data loading ────────────────────────────────────────────────────

    async def _load_analysis_with_owner(
        self, owner_id: uuid.UUID, analysis_id: uuid.UUID
    ) -> tuple[AnalysisRun, Repository]:
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
        stmt = (
            select(Finding)
            .where(Finding.analysis_run_id == analysis_id)
            .order_by(Finding.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def _load_scanner_runs(self, analysis_id: uuid.UUID) -> list[ScannerRun]:
        stmt = (
            select(ScannerRun)
            .where(ScannerRun.analysis_run_id == analysis_id)
            .order_by(ScannerRun.created_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def _find_previous_completed(
        self, repository_id: uuid.UUID, current_id: uuid.UUID
    ) -> AnalysisRun | None:
        stmt = (
            select(AnalysisRun)
            .where(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == AnalysisRunStatus.COMPLETED,
                AnalysisRun.id != current_id,
            )
            .order_by(AnalysisRun.completed_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ── Aggregate building ──────────────────────────────────────────────

    @staticmethod
    def _build_severity_counts(raw: dict[str, int]) -> SeverityCounts:
        return SeverityCounts(
            critical=raw.get("critical", 0),
            high=raw.get("high", 0),
            medium=raw.get("medium", 0),
            low=raw.get("low", 0),
            unknown=raw.get("unknown", 0),
        )

    @staticmethod
    def _build_finding_type_counts(raw: dict[str, int]) -> FindingTypeCounts:
        return FindingTypeCounts(
            vulnerability=raw.get("vulnerability", 0),
            secret=raw.get("secret", 0),
            sast=raw.get("sast", 0),
            license=raw.get("license", 0),
            configuration=raw.get("configuration", 0),
            sbom=raw.get("sbom", 0),
        )

    @staticmethod
    def _build_scanner_counts(raw: dict[str, int]) -> ScannerCounts:
        return ScannerCounts(
            trivy=raw.get("trivy", 0),
            gitleaks=raw.get("gitleaks", 0),
            semgrep=raw.get("semgrep", 0),
            grype=raw.get("grype", 0),
        )

    # ── Risk factors ────────────────────────────────────────────────────

    @staticmethod
    def _generate_risk_factors(
        findings: list[Finding],
        severity_counts: dict[str, int],
        secret_count: int,
        unfixed_count: int,
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        crit = severity_counts.get("critical", 0)
        if crit > 0:
            word = "issue" if crit == 1 else "issues"
            factors.append(
                RiskFactor(
                    category="critical_findings",
                    severity="critical",
                    count=crit,
                    message=f"{crit} critical security {word} detected.",
                )
            )

        high = severity_counts.get("high", 0)
        if high > 0:
            word = "finding" if high == 1 else "findings"
            factors.append(
                RiskFactor(
                    category="high_findings",
                    severity="high",
                    count=high,
                    message=f"{high} high-severity {word} detected.",
                )
            )

        if secret_count > 0:
            word = "secret" if secret_count == 1 else "secrets"
            factors.append(
                RiskFactor(
                    category="secrets",
                    severity="critical",
                    count=secret_count,
                    message=(f"{secret_count} potential {word} detected. Investigate immediately."),
                )
            )

        sast_count = _count_by_type_value(findings, "sast")
        if sast_count > 0:
            word = "finding" if sast_count == 1 else "findings"
            factors.append(
                RiskFactor(
                    category="sast_findings",
                    severity="medium",
                    count=sast_count,
                    message=(f"{sast_count} static analysis {word} in source code."),
                )
            )

        if unfixed_count > 0:
            word = "vulnerability" if unfixed_count == 1 else "vulnerabilities"
            factors.append(
                RiskFactor(
                    category="unfixed_vulnerabilities",
                    severity="high",
                    count=unfixed_count,
                    message=(f"{unfixed_count} {word} with available fixes not applied."),
                )
            )

        vuln_total = _count_by_type_value(findings, "vulnerability")
        has_crit = any(f.category == "critical_findings" for f in factors)
        if vuln_total > 0 and not has_crit:
            word = "vulnerability" if vuln_total == 1 else "vulnerabilities"
            factors.append(
                RiskFactor(
                    category="vulnerabilities",
                    severity="medium",
                    count=vuln_total,
                    message=(f"{vuln_total} {word} detected across dependencies."),
                )
            )

        return factors

    # ── Prioritization ──────────────────────────────────────────────────

    @staticmethod
    def _prioritize_findings(
        findings: list[Finding],
        *,
        limit: int = 10,
    ) -> list[PriorityFinding]:
        severity_order = {
            s: i for i, s in enumerate(["critical", "high", "medium", "low", "unknown"])
        }
        type_priority = {
            "secret": 0,
            "vulnerability": 1,
            "sast": 2,
            "configuration": 3,
            "license": 4,
            "sbom": 5,
        }

        def _sort_key(f: Finding):
            sev = _enum_val(f.severity)
            ftype = _enum_val(f.finding_type)
            has_fix = 0 if f.fixed_version else 1
            return (
                severity_order.get(sev, 99),
                has_fix,
                type_priority.get(ftype, 99),
            )

        sorted_findings = sorted(findings, key=_sort_key)
        result: list[PriorityFinding] = []

        for f in sorted_findings[:limit]:
            sev = _enum_val(f.severity)
            ftype = _enum_val(f.finding_type)
            reason = _priority_reason(f, sev, ftype)

            result.append(
                PriorityFinding(
                    id=str(f.id),
                    title=f.title,
                    severity=sev,
                    finding_type=ftype,
                    scanner=f.scanner,
                    package_name=f.package_name,
                    vulnerability_id=f.vulnerability_id,
                    fixed_version=f.fixed_version,
                    location=f.location,
                    priority_reason=reason,
                )
            )

        return result

    # ── Trend ───────────────────────────────────────────────────────────

    @staticmethod
    def _compute_trend(
        current: list[Finding],
        previous: list[Finding],
        prev_run: AnalysisRun | None,
    ) -> TrendInfo:
        if prev_run is None:
            return TrendInfo(has_previous=False, trend=None)

        cur_total = len(current)
        prev_total = len(previous)
        finding_delta = cur_total - prev_total

        crit_delta = _count_by_severity(current, "critical") - _count_by_severity(
            previous, "critical"
        )
        high_delta = _count_by_severity(current, "high") - _count_by_severity(previous, "high")
        secret_delta = _count_by_type_value(current, "secret") - _count_by_type_value(
            previous, "secret"
        )
        vuln_delta = _count_by_type_value(current, "vulnerability") - _count_by_type_value(
            previous, "vulnerability"
        )

        if finding_delta < 0:
            trend = "improving"
        elif finding_delta > 0:
            trend = "worsening"
        else:
            trend = "unchanged"

        return TrendInfo(
            has_previous=True,
            previous_analysis_id=str(prev_run.id),
            finding_delta=finding_delta,
            critical_delta=crit_delta,
            high_delta=high_delta,
            secret_delta=secret_delta,
            vulnerability_delta=vuln_delta,
            trend=trend,
        )

    # ── Scanner coverage ────────────────────────────────────────────────

    @staticmethod
    def _compute_scanner_coverage(
        scanner_runs: list[ScannerRun],
    ) -> ScannerCoverage:
        total = len(scanner_runs)
        completed = 0
        failed = 0
        skipped = 0
        details: list[ScannerDetail] = []

        for sr in scanner_runs:
            status = _enum_val(sr.status)
            details.append(
                ScannerDetail(
                    name=sr.scanner_name,
                    status=status,
                    finding_count=sr.finding_count,
                    duration_ms=sr.duration_ms,
                    failure_reason=sr.failure_reason,
                )
            )
            if status == "completed":
                completed += 1
            elif status == "failed":
                failed += 1
            elif status in ("skipped", "cancelled"):
                skipped += 1

        pct = (completed / total * 100) if total > 0 else 0.0

        return ScannerCoverage(
            total_scanners=total,
            completed_scanners=completed,
            failed_scanners=failed,
            skipped_scanners=skipped,
            coverage_percentage=round(pct, 1),
            scanner_details=details,
        )

    # ── Summary ─────────────────────────────────────────────────────────

    @staticmethod
    def _generate_summary(
        risk_level: str,
        total_findings: int,
        severity_counts: dict[str, int],
        coverage: ScannerCoverage,
    ) -> str:
        descriptions = {
            "critical": (
                "This repository has critical security risks requiring immediate attention."
            ),
            "high": (
                "This repository has significant security risks that should be addressed urgently."
            ),
            "medium": ("This repository has moderate security risks that should be addressed."),
            "low": ("This repository has minor security issues that should be monitored."),
            "healthy": ("This repository has a good security posture."),
        }
        parts: list[str] = [descriptions.get(risk_level, "Security assessment complete.")]

        if total_findings == 0:
            parts.append("No security findings were detected.")
        else:
            crit = severity_counts.get("critical", 0)
            high = severity_counts.get("high", 0)
            concerns: list[str] = []
            if crit > 0:
                concerns.append(f"{crit} critical")
            if high > 0:
                concerns.append(f"{high} high")
            if concerns:
                parts.append(f"Key concerns: {', '.join(concerns)} findings.")
            parts.append(f"Total findings: {total_findings}.")

        if coverage.failed_scanners > 0:
            parts.append(
                f"Note: {coverage.failed_scanners} of"
                f" {coverage.total_scanners} scanners failed"
                " — results may be incomplete."
            )

        return " ".join(parts)


# ── Helpers ──────────────────────────────────────────────────────────────


def _enum_val(obj: object) -> str:
    """Extract the string value from an enum or return str(obj)."""
    if hasattr(obj, "value"):
        return str(obj.value)  # type: ignore[union-attr]
    return str(obj)


def _count_by_type_value(findings: list[Finding], ftype: str) -> int:
    """Count findings by finding_type value."""
    return sum(1 for f in findings if _enum_val(f.finding_type) == ftype)


def _count_by_severity(findings: list[Finding], severity: str) -> int:
    """Count findings by severity value."""
    return sum(1 for f in findings if _enum_val(f.severity) == severity)


def _priority_reason(f: Finding, sev: str, ftype: str) -> str:
    """Generate a human-readable priority reason."""
    has_fix = bool(f.fixed_version)

    if ftype == "secret":
        return "Secret detected — investigate and rotate immediately."
    if sev == "critical":
        if has_fix:
            return f"Critical severity with fix available in {f.fixed_version}."
        return "Critical severity — no fix version identified."
    if sev == "high":
        if has_fix:
            return f"High severity with fix available in {f.fixed_version}."
        return "High severity finding."
    if ftype == "sast":
        return "Static analysis finding in source code."
    if has_fix:
        return f"Fix available in {f.fixed_version}."
    return f"{sev.title()} severity finding."
