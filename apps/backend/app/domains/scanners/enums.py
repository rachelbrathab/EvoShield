"""Scanner-agnostic enums shared across all scanner adapters.

Severity and finding_type are the two universal dimensions every scanner
contributes to.  Storing them as VARCHAR (not DB enums) keeps the schema
migration-free when new values are added — the same pattern used for
`AnalysisStatus` and `AnalysisRunStatus` (see docs/adr/0006).
"""

from enum import StrEnum


class Severity(StrEnum):
    """Normalized severity of a security finding."""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingType(StrEnum):
    """Category of security finding produced by a scanner.

    Each scanner maps its native finding types into one of these buckets.
    New types are appended here without a migration (VARCHAR column).
    """

    VULNERABILITY = "vulnerability"
    SECRET = "secret"
    SAST = "sast"
    LICENSE = "license"
    CONFIGURATION = "configuration"
    SBOM = "sbom"
