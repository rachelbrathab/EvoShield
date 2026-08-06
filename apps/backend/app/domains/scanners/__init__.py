"""Scanner engine domain (Sprint 5+).

Owns orchestration of the security scanners — Trivy, Syft, Grype, Semgrep,
Gitleaks — and normalization of their output into a unified `Finding` model.

Dependency rule: consumes analysis artifacts; produces findings consumed by
the repository intelligence and recommendation domains. Scanner binaries are
treated as external infrastructure behind a port (see `scanners/ports.py`
when implemented) so tools can be swapped without touching callers.
"""
