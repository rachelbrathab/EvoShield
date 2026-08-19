"""Scanner-domain ports — the seam every scanner adapter implements.

`ScannerProvider` extends `AnalysisProvider` with scanner-specific metadata
(name, version, supported scan types, availability check).  Each real scanner
(Trivy, Syft, Grype, Semgrep, Gitleaks) ships as a separate adapter
implementing this protocol.

`FindingParser` converts a scanner's raw output into `ScannerFinding` objects.
The adapter produces raw output; the parser normalizes it — two distinct
responsibilities following the Single Responsibility Principle.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domains.scanners.enums import FindingType, Severity


class ScannerFinding:
    """Normalized finding produced by any scanner adapter.

    This is the *internal* representation stored in the `findings` table.
    Every scanner maps its native output onto these fields.
    """

    def __init__(
        self,
        *,
        analysis_run_id: uuid.UUID,
        scanner: str,
        scanner_version: str,
        finding_type: FindingType,
        severity: Severity,
        title: str,
        description: str | None = None,
        package_name: str | None = None,
        installed_version: str | None = None,
        fixed_version: str | None = None,
        vulnerability_id: str | None = None,
        references: list[str] | None = None,
        location: str | None = None,
    ) -> None:
        self.analysis_run_id = analysis_run_id
        self.scanner = scanner
        self.scanner_version = scanner_version
        self.finding_type = finding_type
        self.severity = severity
        self.title = title
        self.description = description
        self.package_name = package_name
        self.installed_version = installed_version
        self.fixed_version = fixed_version
        self.vulnerability_id = vulnerability_id
        self.references = references or []
        self.location = location


class ScannerProvider(Protocol):
    """Port every scanner adapter implements.

    Extends `AnalysisProvider` from the analysis domain with scanner-specific
    capabilities.  The orchestrator sees `AnalysisProvider`; the scanner
    infrastructure sees `ScannerProvider`.
    """

    name: str
    version: str
    supported_types: list[FindingType]

    def is_available(self) -> bool:
        """Whether the scanner binary is installed and reachable."""
        ...

    def get_version(self) -> str | None:
        """Return the installed scanner version, or None if unavailable."""
        ...

    async def scan_filesystem(
        self,
        path: str,
        *,
        cancel_event: object | None = None,
    ) -> list[ScannerFinding]:
        """Scan a directory and return normalized findings."""
        ...


class FindingParser(Protocol):
    """Converts a scanner's raw output into ScannerFinding objects."""

    def parse(self, raw_output: str, *, analysis_run_id: uuid.UUID) -> list[ScannerFinding]:
        """Parse the raw scanner output and return normalized findings."""
        ...
