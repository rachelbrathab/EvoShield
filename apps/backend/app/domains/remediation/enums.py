"""Remediation enums — finding status and fix availability.

Stored as VARCHAR (no DB CHECK constraint) following the project convention
established by AnalysisStatus, AnalysisRunStatus, Severity, and FindingType.
New values are code-only additions — no migration required.
"""

from enum import StrEnum


class FindingStatus(StrEnum):
    """Lifecycle status of a security finding.

    Default is OPEN. Users may transition to ACKNOWLEDGED, RESOLVED,
    or FALSE_POSITIVE. The status is mutable; the Finding itself is not.
    """

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class FixAvailability(StrEnum):
    """Whether a known fix exists for a finding."""

    FIX_AVAILABLE = "fix_available"
    NO_KNOWN_FIX = "no_known_fix"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
