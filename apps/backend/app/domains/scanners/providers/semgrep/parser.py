"""Semgrep JSON output parser — normalized finding extraction.

Converts Semgrep's JSON output into normalized ``ScannerFinding`` objects.

Semgrep JSON structure (``semgrep scan --json``):
```json
{
  "results": [
    {
      "check_id": "python.lang.security.audit.dangerous-subprocess-call",
      "path": "app/utils.py",
      "start": { "line": 42, "col": 5 },
      "end": { "line": 42, "col": 40 },
      "extra": {
        "message": "Dangerous subprocess call detected",
        "severity": "ERROR",
        "metadata": {
          "cwe": ["CWE-78"],
          "owasp": ["A01:2021"],
          "confidence": "HIGH",
          "impact": "HIGH"
        }
      }
    }
  ],
  "errors": [],
  "stats": { ... }
}
```

SECURITY: Source code snippets in ``extra.lines`` or ``extra.lines_of_code``
are NOT persisted.  Only safe metadata is retained.
"""

import json
import logging
import uuid

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.ports import ScannerFinding

logger = logging.getLogger(__name__)

# Semgrep severity mapping to normalized severity levels.
_SEVERITY_MAP: dict[str, Severity] = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
    "UNKNWON": Severity.UNKNOWN,
}

# Default severity when Semgrep doesn't specify one.
_DEFAULT_SEVERITY = Severity.MEDIUM


def _map_severity(semgrep_severity: str | None) -> Severity:
    """Map a Semgrep severity string to a normalized Severity enum."""
    if not semgrep_severity:
        return _DEFAULT_SEVERITY
    return _SEVERITY_MAP.get(semgrep_severity.upper(), _DEFAULT_SEVERITY)


class SemgrepResultParser:
    """Parse Semgrep JSON output into ScannerFinding objects.

    SECURITY: Source code snippets (``extra.lines``, ``extra.lines_of_code``)
    are NEVER included in the output.  Only safe metadata is retained.
    """

    def __init__(
        self,
        *,
        scanner_name: str = "semgrep",
        scanner_version: str = "0.1.0",
    ) -> None:
        self._scanner_name = scanner_name
        self._scanner_version = scanner_version

    def parse(
        self,
        raw_output: str,
        *,
        analysis_run_id: uuid.UUID,
    ) -> list[ScannerFinding]:
        """Parse Semgrep JSON output and return normalized findings.

        Args:
            raw_output: The raw JSON string from Semgrep stdout.
            analysis_run_id: The ID of the analysis run.

        Returns:
            List of normalized ScannerFinding objects.
        """
        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse Semgrep JSON output")
            return []

        if not isinstance(data, dict):
            return []

        results_raw = data.get("results") or []
        if not isinstance(results_raw, list):
            return []

        findings: list[ScannerFinding] = []

        for item in results_raw:
            finding = self._parse_finding(
                item,
                analysis_run_id=analysis_run_id,
            )
            if finding is not None:
                findings.append(finding)

        logger.info(
            "Parsed %d SAST findings from Semgrep output (run=%s)",
            len(findings),
            analysis_run_id,
        )
        return findings

    def _parse_finding(
        self,
        item: dict,
        *,
        analysis_run_id: uuid.UUID,
    ) -> ScannerFinding | None:
        """Parse a single Semgrep finding.

        Returns None if the entry is missing required fields.

        SECURITY: Source code snippets are NEVER included in the output.
        """
        check_id = item.get("check_id") or ""
        if not check_id:
            return None

        extra = item.get("extra") or {}
        message = extra.get("message") or f"Semgrep finding: {check_id}"
        semgrep_severity = extra.get("severity")
        severity = _map_severity(semgrep_severity)

        # Extract metadata
        metadata = extra.get("metadata") or {}

        # Build a safe location string: "file:line-col"
        path = item.get("path") or ""
        start = item.get("start") or {}
        start_line = start.get("line")
        start_col = start.get("col")

        location = path
        if path and start_line is not None:
            location = f"{path}:{start_line}"
            if start_col is not None:
                location = f"{path}:{start_line}:{start_col}"

        # Build references from CWE/OWASP metadata.
        references: list[str] = []
        cwe_list = metadata.get("cwe") or []
        if isinstance(cwe_list, list):
            for cwe in cwe_list:
                if isinstance(cwe, str) and cwe:
                    references.append(cwe)

        owasp_list = metadata.get("owasp") or []
        if isinstance(owasp_list, list):
            for owasp in owasp_list:
                if isinstance(owasp, str) and owasp:
                    references.append(f"owasp:{owasp}")

        # Build title: use check_id as the human-readable identifier.
        title = check_id

        return ScannerFinding(
            analysis_run_id=analysis_run_id,
            scanner=self._scanner_name,
            scanner_version=self._scanner_version,
            finding_type=FindingType.SAST,
            severity=severity,
            title=title[:512],
            description=message[:2048] or None,
            package_name=None,
            installed_version=None,
            fixed_version=None,
            vulnerability_id=None,
            references=references,
            location=location[:1024] or None,
        )
