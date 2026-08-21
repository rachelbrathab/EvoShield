"""Intelligence API response schemas — clean wire contracts.

These define the exact shape of the intelligence endpoint response.
No raw scanner output, no secrets, no source code.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SeverityCounts(BaseModel):
    """Finding counts by severity level."""

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    unknown: int = 0


class FindingTypeCounts(BaseModel):
    """Finding counts by finding type."""

    vulnerability: int = 0
    secret: int = 0
    sast: int = 0
    license: int = 0
    configuration: int = 0
    sbom: int = 0


class ScannerCounts(BaseModel):
    """Finding counts by scanner name."""

    trivy: int = 0
    gitleaks: int = 0
    semgrep: int = 0
    grype: int = 0


class RiskFactor(BaseModel):
    """A single categorized risk factor with explanation."""

    category: str = Field(description="Risk category (e.g. 'secrets', 'critical_vulns')")
    severity: str = Field(description="Severity level of this factor")
    count: int = Field(description="Number of findings in this category")
    message: str = Field(description="Human-readable explanation")


class PriorityFinding(BaseModel):
    """A prioritized finding — safe metadata only, no secrets or source code."""

    id: str = Field(description="Finding ID")
    title: str = Field(description="Finding title")
    severity: str = Field(description="Severity level")
    finding_type: str = Field(description="Finding type (vulnerability, secret, sast)")
    scanner: str = Field(description="Scanner that produced this finding")
    package_name: str | None = Field(default=None, description="Affected package")
    vulnerability_id: str | None = Field(default=None, description="CVE/GHSA ID")
    fixed_version: str | None = Field(default=None, description="Available fix version")
    location: str | None = Field(default=None, description="File or package location")
    priority_reason: str = Field(description="Why this finding is prioritized")


class TrendInfo(BaseModel):
    """Comparison with the previous analysis run."""

    has_previous: bool = Field(description="Whether a previous completed analysis exists")
    previous_analysis_id: str | None = Field(default=None, description="Previous analysis run ID")
    finding_delta: int | None = Field(default=None, description="Change in total findings")
    critical_delta: int | None = Field(default=None, description="Change in critical findings")
    high_delta: int | None = Field(default=None, description="Change in high findings")
    secret_delta: int | None = Field(default=None, description="Change in secret findings")
    vulnerability_delta: int | None = Field(
        default=None, description="Change in vulnerability findings"
    )
    trend: str | None = Field(
        default=None,
        description="'improving', 'worsening', or 'unchanged'",
    )


class ScannerCoverage(BaseModel):
    """Scanner execution coverage for this analysis."""

    total_scanners: int = Field(description="Total configured scanners")
    completed_scanners: int = Field(description="Scanners that completed successfully")
    failed_scanners: int = Field(description="Scanners that failed")
    skipped_scanners: int = Field(description="Scanners that were skipped or cancelled")
    coverage_percentage: float = Field(description="Percentage of scanners that completed [0-100]")
    scanner_details: list[ScannerDetail] = Field(
        default_factory=list, description="Per-scanner status"
    )


class ScannerDetail(BaseModel):
    """Status of a single scanner in this analysis."""

    name: str
    status: str
    finding_count: int | None = None
    duration_ms: int | None = None
    failure_reason: str | None = None


# Rebuild models that reference each other
ScannerCoverage.model_rebuild()


class RemediationMetrics(BaseModel):
    """Remediation metrics integrated into intelligence response."""

    open_count: int = Field(description="Findings in OPEN status")
    acknowledged_count: int = Field(description="Findings in ACKNOWLEDGED status")
    resolved_count: int = Field(description="Findings in RESOLVED status")
    false_positive_count: int = Field(description="Findings marked as FALSE_POSITIVE")
    fixable_count: int = Field(description="Findings with a known fix available")
    remediation_rate: float = Field(
        description="Percentage of findings resolved or false positive [0-100]"
    )


class RepositoryIntelligence(BaseModel):
    """Complete repository intelligence response.

    This is the primary API response for the intelligence endpoint.
    It aggregates evidence from all scanners into actionable insight.
    """

    repository_id: str = Field(description="Repository ID")
    analysis_id: str = Field(description="Analysis run ID")
    generated_at: str = Field(description="ISO timestamp of intelligence generation")

    # Overall risk
    risk_score: float = Field(description="Risk score [0-100]. Lower = higher risk.")
    risk_level: str = Field(description="Risk level: critical, high, medium, low, healthy")

    # Analysis health
    analysis_status: str = Field(description="Status of the analysis run")

    # Aggregated counts
    total_findings: int = Field(description="Total finding count")
    severity_counts: SeverityCounts = Field(description="Findings by severity")
    finding_type_counts: FindingTypeCounts = Field(description="Findings by type")
    scanner_counts: ScannerCounts = Field(description="Findings by scanner")

    # Risk assessment
    risk_factors: list[RiskFactor] = Field(description="Categorized risk factors")
    top_findings: list[PriorityFinding] = Field(
        description="Prioritized findings to investigate first"
    )

    # Remediation metrics (Sprint 7)
    remediation_metrics: RemediationMetrics = Field(description="Remediation status and progress")

    # Trend
    trend: TrendInfo = Field(description="Comparison with previous analysis")

    # Scanner coverage
    scanner_coverage: ScannerCoverage = Field(description="Scanner execution coverage")

    # Summary
    summary: str = Field(description="Human-readable summary of the intelligence")
