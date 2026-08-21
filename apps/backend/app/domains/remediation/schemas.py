"""Remediation API response schemas — clean wire contracts.

Defines the shape of remediation endpoint responses.
No raw scanner output, no secrets, no source code.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RemediationGuidance(BaseModel):
    """Deterministic remediation guidance for a finding."""

    summary: str = Field(description="Why this finding matters")
    recommendation: str = Field(description="What to do about it")
    steps: list[str] = Field(description="Ordered remediation steps")


class FindingRemediation(BaseModel):
    """Complete remediation information for a single finding."""

    finding_id: str = Field(description="Finding ID")
    severity: str = Field(description="Finding severity")
    finding_type: str = Field(description="Finding type")
    scanner: str = Field(description="Scanner that produced this finding")
    title: str = Field(description="Finding title")
    status: str = Field(description="Current remediation status")
    priority: int = Field(description="Remediation priority (lower = higher priority)")
    fix_availability: str = Field(description="Whether a fix is available")
    package_name: str | None = Field(default=None, description="Affected package")
    installed_version: str | None = Field(default=None, description="Installed version")
    fixed_version: str | None = Field(default=None, description="Fixed version")
    vulnerability_id: str | None = Field(default=None, description="CVE/GHSA ID")
    location: str | None = Field(default=None, description="File or package location")
    guidance: RemediationGuidance = Field(description="Remediation guidance")


class RemediationStatusUpdate(BaseModel):
    """Request to update a finding's remediation status."""

    status: str = Field(description="New status: acknowledged, resolved, false_positive")
    note: str | None = Field(default=None, description="Optional note")


class RemediationStatusResponse(BaseModel):
    """Response after updating a finding's status."""

    finding_id: str
    status: str
    updated_at: str


class RemediationSummary(BaseModel):
    """Aggregated remediation metrics for an analysis run."""

    total_findings: int = Field(description="Total finding count")
    open_count: int = Field(description="Findings in OPEN status")
    acknowledged_count: int = Field(description="Findings in ACKNOWLEDGED status")
    resolved_count: int = Field(description="Findings in RESOLVED status")
    false_positive_count: int = Field(description="Findings in FALSE_POSITIVE status")
    fixable_count: int = Field(description="Findings with a known fix available")
    unfixable_count: int = Field(description="Findings with no known fix")
    remediation_rate: float = Field(
        description="Percentage of findings resolved or marked false positive [0-100]"
    )
    critical_open: int = Field(description="Open critical-severity findings")
    high_open: int = Field(description="Open high-severity findings")


class AnalysisRemediation(BaseModel):
    """Complete remediation intelligence for an analysis run."""

    analysis_id: str = Field(description="Analysis run ID")
    repository_id: str = Field(description="Repository ID")
    summary: RemediationSummary = Field(description="Remediation metrics")
    findings: list[FindingRemediation] = Field(description="Findings with remediation guidance")
