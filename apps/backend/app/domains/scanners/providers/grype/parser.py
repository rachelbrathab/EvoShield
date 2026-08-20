"""Grype JSON output parser — normalizes vulnerability results.

Converts Grype's JSON output into normalized ``ScannerFinding`` objects.
Grype produces a structured vulnerability report with matched CVEs,
affected packages, severity, and fix versions.

Grype JSON structure (simplified):
```json
{
  "matches": [
    {
      "vulnerability": {
        "id": "CVE-2024-1234",
        "severity": "High",
        "description": "...",
        "fix": { "versions": ["1.2.3"] }
      },
      "artifact": {
        "name": "requests",
        "version": "2.28.0",
        "type": "python"
      }
    }
  ]
}
```

SECURITY: Raw scanner output is never persisted. Only normalized
finding metadata (CVE ID, package, version, severity) is retained.
"""

import json
import logging
import uuid

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.ports import ScannerFinding

logger = logging.getLogger(__name__)

# Map Grype severity strings to our Severity enum.
_SEVERITY_MAP: dict[str, Severity] = {
    "Critical": Severity.CRITICAL,
    "High": Severity.HIGH,
    "Medium": Severity.MEDIUM,
    "Low": Severity.LOW,
    "Negligible": Severity.LOW,
    "Unknown": Severity.UNKNOWN,
}

# Map Grype ecosystem/type strings to human-readable labels.
_ECOSYSTEM_MAP: dict[str, str] = {
    "python": "PyPI",
    "npm": "npm",
    "go": "Go",
    "cargo": "Rust",
    "gem": "RubyGems",
    "maven": "Maven",
    "nuget": "NuGet",
    "deb": "Debian",
    "rpm": "RPM",
}


def _map_severity(raw: str | None) -> Severity:
    """Map a Grype severity string to our Severity enum."""
    if not raw:
        return Severity.UNKNOWN
    return _SEVERITY_MAP.get(raw, Severity.UNKNOWN)


def _map_ecosystem(raw: str | None) -> str | None:
    """Map a Grype artifact type to a human-readable ecosystem label."""
    if not raw:
        return None
    return _ECOSYSTEM_MAP.get(raw.lower(), raw)


class GrypeResultParser:
    """Parse Grype JSON output into ScannerFinding objects.

    SECURITY: Raw output is never persisted. Only safe metadata
    (CVE ID, package name, version, severity, fix version) is retained.
    """

    def __init__(
        self,
        *,
        scanner_name: str = "grype",
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
        """Parse Grype JSON output and return normalized findings.

        Args:
            raw_output: The raw JSON string from Grype stdout.
            analysis_run_id: The ID of the analysis run.

        Returns:
            List of normalized ScannerFinding objects.
        """
        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse Grype JSON output")
            return []

        # Grype returns {"matches": [...]} with vulnerability details.
        matches = data.get("matches") if isinstance(data, dict) else None
        if matches is None:
            # Try direct list (some Grype versions/configs).
            if isinstance(data, list):
                matches = data
            else:
                return []

        # Validate matches is actually a list of dicts.
        if not isinstance(matches, list):
            return []

        findings: list[ScannerFinding] = []

        for match in matches:
            finding = self._parse_match(
                match,
                analysis_run_id=analysis_run_id,
            )
            if finding is not None:
                findings.append(finding)

        logger.info(
            "Parsed %d vulnerability findings from Grype output (run=%s)",
            len(findings),
            analysis_run_id,
        )
        return findings

    def _parse_match(
        self,
        match: dict,
        *,
        analysis_run_id: uuid.UUID,
    ) -> ScannerFinding | None:
        """Parse a single Grype match entry.

        Returns None if the entry is missing required fields.
        """
        vuln = match.get("vulnerability") or {}
        artifact = match.get("artifact") or {}

        vuln_id = vuln.get("id") or ""
        if not vuln_id:
            return None

        package_name = artifact.get("name") or ""
        installed_version = artifact.get("version") or None
        artifact_type = artifact.get("type") or None

        # Fix versions
        fix_info = vuln.get("fix") or {}
        fix_versions = fix_info.get("versions") or []
        fixed_version = fix_versions[0] if fix_versions else None

        severity = _map_severity(vuln.get("severity"))
        ecosystem = _map_ecosystem(artifact_type)

        # Build a safe title — no raw scanner output.
        if package_name:
            title = f"{vuln_id} in {package_name}"
        else:
            title = vuln_id

        # Build description from vuln description (safe metadata).
        description = vuln.get("description") or None
        if description and len(description) > 2048:
            description = description[:2048]

        # Build references from vuln URLs.
        references: list[str] = []
        for url in vuln.get("urls") or []:
            if isinstance(url, str) and url.startswith("http"):
                references.append(url)
        # Add NVD link as fallback reference.
        if not references and vuln_id.startswith("CVE-"):
            references.append(f"https://nvd.nist.gov/vuln/detail/{vuln_id}")

        # Build location from package + ecosystem.
        location = None
        if package_name and ecosystem:
            location = f"{ecosystem}:{package_name}"
        elif package_name:
            location = package_name

        # Build a rich description with fix info.
        desc_parts: list[str] = []
        if description:
            desc_parts.append(description)
        if installed_version:
            desc_parts.append(f"Installed version: {installed_version}")
        if fixed_version:
            desc_parts.append(f"Fix available: {fixed_version}")
        elif fix_versions:
            desc_parts.append(f"Fix available: {', '.join(fix_versions)}")
        if ecosystem:
            desc_parts.append(f"Ecosystem: {ecosystem}")

        enriched_description = " | ".join(desc_parts) if desc_parts else None

        return ScannerFinding(
            analysis_run_id=analysis_run_id,
            scanner=self._scanner_name,
            scanner_version=self._scanner_version,
            finding_type=FindingType.VULNERABILITY,
            severity=severity,
            title=title[:512],
            description=enriched_description[:2048] if enriched_description else None,
            package_name=package_name or None,
            installed_version=installed_version,
            fixed_version=fixed_version,
            vulnerability_id=vuln_id,
            references=references,
            location=location[:1024] if location else None,
        )
