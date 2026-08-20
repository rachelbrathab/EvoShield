"""Grype vulnerability scanner provider — Syft + Grype SBOM pipeline.

This package integrates Grype (SBOM-based vulnerability matching) through
the existing ScannerRun architecture. Internally it invokes Syft to generate
a transient SBOM, then feeds it to Grype for vulnerability detection.

Security: The SBOM is a temporary file deleted after parsing. Raw scanner
output is never persisted or exposed through the API.
"""
