"""Gitleaks JSON output parser with MANDATORY secret redaction.

Converts Gitleaks' JSON output into normalized ``ScannerFinding`` objects.
The parser enforces a critical security invariant:

    **The actual secret value must NEVER appear in any output.**

Gitleaks JSON structure (per finding):
```json
{
  "RuleID": "github-personal-access-token",
  "Description": "detected a GitHub Personal Access Token",
  "StartLine": 42,
  "EndLine": 42,
  "StartColumn": 15,
  "EndColumn": 55,
  "Match": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij",
  "File": "config/settings.py",
  "Commit": "abc123def456...",
  "Author": "developer",
  "Email": "dev@example.com",
  "Message": "update config",
  "Date": "2024-01-15T10:30:00Z",
  "Fingerprint": "abc123:config/settings.py:github-personal-access-token"
}
```

The ``Match`` field contains the actual secret — it is DISCARDED during
parsing.  Only safe metadata is preserved.
"""

import json
import logging
import uuid

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.ports import ScannerFinding

logger = logging.getLogger(__name__)

# Gitleaks severity heuristic: map rule descriptions to severity levels.
# Gitleaks itself doesn't assign severity, so we infer from the rule type.
_RULE_SEVERITY: dict[str, Severity] = {
    # High-severity tokens / keys
    "github-personal-access-token": Severity.HIGH,
    "github-oauth-access-token": Severity.HIGH,
    "github-app-token": Severity.HIGH,
    "aws-access-key": Severity.HIGH,
    "aws-secret-key": Severity.CRITICAL,
    "private-key": Severity.CRITICAL,
    "generic-api-key": Severity.HIGH,
    "slack-webhook-url": Severity.MEDIUM,
    "stripe-secret-key": Severity.CRITICAL,
    "sendgrid-api-key": Severity.HIGH,
    "twilio-api-key": Severity.HIGH,
    "heroku-api-key": Severity.HIGH,
    "google-api-key": Severity.HIGH,
    "google-oauth-access-token": Severity.HIGH,
    "facebook-secret": Severity.HIGH,
    "twitter-secret": Severity.HIGH,
    # Medium-severity patterns
    "password": Severity.MEDIUM,
    "secret": Severity.MEDIUM,
    "token": Severity.MEDIUM,
    # Default for unknown rules
}


def _infer_severity(rule_id: str) -> Severity:
    """Infer severity from Gitleaks rule ID.

    Checks for known high-risk patterns.  Falls back to MEDIUM for
    unrecognized rules — a conservative default.
    """
    rule_lower = rule_id.lower()
    for pattern, severity in _RULE_SEVERITY.items():
        if pattern in rule_lower:
            return severity
    return Severity.MEDIUM


class GitleaksResultParser:
    """Parse Gitleaks JSON output into ScannerFinding objects.

    SECURITY: The ``Match`` field (actual secret) is DISCARDED.
    Only safe metadata (rule ID, file, line, fingerprint) is preserved.
    """

    def __init__(
        self,
        *,
        scanner_name: str = "gitleaks",
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
        """Parse Gitleaks JSON output and return normalized findings.

        SECURITY: The ``Match`` field is intentionally discarded.
        Only safe metadata is retained.

        Args:
            raw_output: The raw JSON string from Gitleaks stdout.
            analysis_run_id: The ID of the analysis run.

        Returns:
            List of normalized ScannerFinding objects (secrets redacted).
        """
        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse Gitleaks JSON output")
            return []

        # Gitleaks returns a JSON array of finding objects.
        if isinstance(data, dict):
            findings_raw = data.get("findings") or []
        elif isinstance(data, list):
            findings_raw = data
        else:
            return []

        findings: list[ScannerFinding] = []

        for item in findings_raw:
            finding = self._parse_finding(
                item,
                analysis_run_id=analysis_run_id,
            )
            if finding is not None:
                findings.append(finding)

        logger.info(
            "Parsed %d secret findings from Gitleaks output (run=%s)",
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
        """Parse a single Gitleaks finding.

        Returns None if the entry is missing required fields.

        SECURITY: The ``Match`` field is NEVER included in the output.
        """
        rule_id = item.get("RuleID") or ""
        if not rule_id:
            return None

        description = item.get("Description") or f"Secret detected by rule: {rule_id}"
        severity = _infer_severity(rule_id)

        # Build a safe location string: "file:line" without the secret.
        file_path = item.get("File") or ""
        start_line = item.get("StartLine")
        location = file_path
        if file_path and start_line is not None:
            location = f"{file_path}:{start_line}"

        # Build reference from commit if available.
        references: list[str] = []
        commit = item.get("Commit")
        if commit and len(commit) >= 8:
            # Include short commit hash as a reference — no secret involved.
            references.append(f"commit:{commit[:12]}")

        # Fingerprint is safe to preserve — it's a hash, not the secret.
        # (Not stored in the Finding model currently; reserved for future use.)

        # SECURITY: Build a title that does NOT contain the secret.
        # Use rule ID and file, never the Match value.
        title = f"Secret detected: {rule_id}"
        if file_path:
            title = f"Secret detected in {file_path}: {rule_id}"

        return ScannerFinding(
            analysis_run_id=analysis_run_id,
            scanner=self._scanner_name,
            scanner_version=self._scanner_version,
            finding_type=FindingType.SECRET,
            severity=severity,
            title=title[:512],
            description=description[:2048] or None,
            package_name=None,
            installed_version=None,
            fixed_version=None,
            vulnerability_id=None,
            references=references,
            location=location[:1024] or None,
        )
