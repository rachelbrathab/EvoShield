"""Trivy JSON output parser.

Converts Trivy's `--format json` output into normalized `ScannerFinding`
objects.  Handles Trivy's nested structure:

```json
{
  "SchemaVersion": "...",
  "Results": [
    {
      "Target": "...",
      "Class": "os-pkgs" | "lang-pkgs",
      "Type": "alpine" | "python" | ...,
      "Vulnerabilities": [
        {
          "VulnerabilityID": "CVE-...",
          "Severity": "HIGH",
          "Title": "...",
          "Description": "...",
          "PkgName": "...",
          "InstalledVersion": "...",
          "FixedVersion": "...",
          "PrimaryURL": "...",
          "References": ["..."]
        }
      ]
    }
  ]
}
```

The parser is resilient: missing fields, empty results, and malformed
entries are skipped without raising — a single bad finding should not
abort the entire scan.
"""

import logging
import uuid

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.ports import ScannerFinding

logger = logging.getLogger(__name__)

# Trivy severity strings → our Severity enum
_SEVERITY_MAP: dict[str, Severity] = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "UNKNOWN": Severity.UNKNOWN,
    "": Severity.UNKNOWN,
}


class TrivyResultParser:
    """Parse Trivy JSON output into ScannerFinding objects."""

    def __init__(
        self,
        *,
        scanner_name: str = "trivy",
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
        """Parse Trivy JSON output and return normalized findings.

        Args:
            raw_output: The raw JSON string from Trivy's stdout.
            analysis_run_id: The ID of the analysis run these findings belong to.

        Returns:
            List of normalized ScannerFinding objects.
        """
        import json

        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse Trivy JSON output")
            return []

        results = data.get("Results") or []
        findings: list[ScannerFinding] = []

        for result in results:
            target = result.get("Target", "")
            vulnerabilities = result.get("Vulnerabilities") or []

            for vuln in vulnerabilities:
                finding = self._parse_vulnerability(
                    vuln,
                    analysis_run_id=analysis_run_id,
                    target=target,
                )
                if finding is not None:
                    findings.append(finding)

        logger.info(
            "Parsed %d findings from Trivy output (run=%s)",
            len(findings),
            analysis_run_id,
        )
        return findings

    def _parse_vulnerability(
        self,
        vuln: dict,
        *,
        analysis_run_id: uuid.UUID,
        target: str,
    ) -> ScannerFinding | None:
        """Parse a single vulnerability entry from Trivy output.

        Returns None if the entry is missing required fields or is invalid.
        """
        vuln_id = vuln.get("VulnerabilityID")
        if not vuln_id:
            return None

        title = vuln.get("Title") or vuln.get("VulnerabilityID") or "Unknown vulnerability"
        severity_str = (vuln.get("Severity") or "").upper()
        severity = _SEVERITY_MAP.get(severity_str, Severity.UNKNOWN)

        # Collect references
        references: list[str] = []
        primary_url = vuln.get("PrimaryURL")
        if primary_url:
            references.append(primary_url)
        for ref in vuln.get("References") or []:
            if ref and ref not in references:
                references.append(ref)

        return ScannerFinding(
            analysis_run_id=analysis_run_id,
            scanner=self._scanner_name,
            scanner_version=self._scanner_version,
            finding_type=FindingType.VULNERABILITY,
            severity=severity,
            title=title[:512],
            description=(vuln.get("Description") or "")[:2048] or None,
            package_name=vuln.get("PkgName"),
            installed_version=vuln.get("InstalledVersion"),
            fixed_version=vuln.get("FixedVersion") or None,
            vulnerability_id=vuln_id,
            references=references,
            location=target or None,
        )
