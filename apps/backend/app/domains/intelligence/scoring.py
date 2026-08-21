"""Deterministic risk scoring — transparent engineering heuristic.

This module computes a repository risk score from normalized finding data.

IMPORTANT: This is NOT a validated security standard. It is a transparent
engineering heuristic that provides a reproducible, explainable score.

Severity weights (impact per finding):
- CRITICAL: 25 points
- HIGH:     15 points
- MEDIUM:    8 points
- LOW:       2 points
- UNKNOWN:   1 point

Additional penalties:
- Secrets detected: +20 (secrets are high-risk regardless of count)
- Unfixed vulnerabilities: +5 per unfixed vuln with a fix available

Risk levels (derived from score):
- critical:  0-20   (immediate action required)
- high:     21-40   (urgent attention needed)
- medium:   41-60   (should be addressed)
- low:      61-80   (minor issues, monitor)
- healthy:  81-100  (good security posture)
"""

from __future__ import annotations

from typing import Any

from app.domains.scanners.enums import FindingType, Severity

# Severity impact weights
_SEVERITY_WEIGHTS: dict[str, float] = {
    Severity.CRITICAL: 25.0,
    Severity.HIGH: 15.0,
    Severity.MEDIUM: 8.0,
    Severity.LOW: 2.0,
    Severity.UNKNOWN: 1.0,
}

# Risk level thresholds (score -> level)
_RISK_LEVELS: list[tuple[float, str]] = [
    (20.0, "critical"),
    (40.0, "high"),
    (60.0, "medium"),
    (80.0, "low"),
    (100.0, "healthy"),
]

_SECRET_PENALTY = 20.0
_UNFIXED_VULN_PENALTY = 5.0


def _safe_enum_value(obj: Any) -> str:
    """Safely extract a string value from an enum or string."""
    if hasattr(obj, "value"):
        return str(obj.value)
    return str(obj)


def compute_risk_score(
    *,
    severity_counts: dict[str, int],
    secret_count: int,
    unfixed_vuln_count: int,
) -> float:
    """Compute a deterministic risk score [0-100].

    Lower score = higher risk. This is a transparent engineering heuristic.
    """
    score = 100.0

    for severity_name, count in severity_counts.items():
        weight = _SEVERITY_WEIGHTS.get(severity_name, 1.0)
        score -= weight * count

    if secret_count > 0:
        score -= _SECRET_PENALTY

    score -= _UNFIXED_VULN_PENALTY * unfixed_vuln_count

    return max(0.0, min(100.0, score))


def compute_risk_level(score: float) -> str:
    """Map a risk score to a risk level."""
    for threshold, level in _RISK_LEVELS:
        if score <= threshold:
            return level
    return "healthy"


def count_unfixed_vulns(findings: list[Any]) -> int:
    """Count vulnerability findings where a fix is available."""
    count = 0
    for f in findings:
        ftype = _safe_enum_value(getattr(f, "finding_type", ""))
        if ftype != FindingType.VULNERABILITY:
            continue
        vuln_id = getattr(f, "vulnerability_id", None)
        fixed = getattr(f, "fixed_version", None)
        if vuln_id and fixed:
            count += 1
    return count


def count_secrets(findings: list[Any]) -> int:
    """Count secret findings."""
    count = 0
    for f in findings:
        ftype = _safe_enum_value(getattr(f, "finding_type", ""))
        if ftype == FindingType.SECRET:
            count += 1
    return count


def aggregate_severities(findings: list[Any]) -> dict[str, int]:
    """Count findings by severity level."""
    counts: dict[str, int] = {}
    for f in findings:
        sev = _safe_enum_value(getattr(f, "severity", "unknown"))
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def aggregate_by_type(findings: list[Any]) -> dict[str, int]:
    """Count findings by finding type."""
    counts: dict[str, int] = {}
    for f in findings:
        ftype = _safe_enum_value(getattr(f, "finding_type", "unknown"))
        counts[ftype] = counts.get(ftype, 0) + 1
    return counts


def aggregate_by_scanner(findings: list[Any]) -> dict[str, int]:
    """Count findings by scanner name."""
    counts: dict[str, int] = {}
    for f in findings:
        scanner = str(getattr(f, "scanner", "unknown"))
        counts[scanner] = counts.get(scanner, 0) + 1
    return counts
