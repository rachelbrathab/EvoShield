"""Remediation domain — deterministic finding lifecycle and remediation intelligence.

Provides:
- Finding lifecycle status (OPEN → ACKNOWLEDGED → RESOLVED / FALSE_POSITIVE)
- Deterministic remediation guidance per finding type
- Fix availability assessment
- Remediation-aware prioritization
- Historical remediation tracking

All guidance is rule-based. No LLM, no ML, no prediction.
"""
