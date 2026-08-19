"""Scanner engine domain (Sprint 5+).

Owns orchestration of the security scanners — Trivy, Syft, Grype, Semgrep,
Gitleaks — and normalization of their output into a unified `Finding` model.

Dependency rule: consumes analysis artifacts; produces findings consumed by
the repository intelligence and recommendation domains. Scanner binaries are
treated as external infrastructure behind a port (see `ports.py`) so tools
can be swapped without touching callers.

Architecture:
    ScannerProvider → FindingParser → ScannerFinding → Finding (ORM)
"""

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.ports import ScannerFinding, ScannerProvider
from app.domains.scanners.workspace import ScannerWorkspace

__all__ = [
    "FindingType",
    "ScannerFinding",
    "ScannerProvider",
    "ScannerWorkspace",
    "Severity",
]
