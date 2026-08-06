"""Reports domain (Sprint 9+).

Owns report generation and export (PDF/HTML/CSV) across repositories,
findings, predictions and recommendations.

Dependency rule: consumes data from sibling domains through the
orchestration layer; never queries their internals directly.
"""
