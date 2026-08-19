"""Gitleaks secret detection scanner provider.

Integrates Gitleaks behind the existing ``AnalysisProvider`` / ``ScannerProvider``
port.  Gitleaks-specific logic is entirely isolated inside this package:

- ``GitleaksRunner`` executes the CLI safely (no shell=True, argument arrays)
- ``GitleaksResultParser`` normalizes JSON output into ``ScannerFinding`` objects
  with **mandatory secret redaction** — the actual secret value must never
  be persisted, logged, or returned through any API surface.

The orchestrator calls ``execute(context)`` — it never knows about Gitleaks.
"""
