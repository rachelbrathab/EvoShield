"""Tests for the Gitleaks result parser — including CRITICAL secret redaction.

The most important test: verify that the literal string "SUPER_SECRET_TEST_VALUE"
never appears in any normalized Finding produced by the parser.
"""

import json
import uuid

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.providers.gitleaks.parser import (
    GitleaksResultParser,
    _infer_severity,
)

# Sentinel used to prove secrets are never leaked.
_FAKE_SECRET = "SUPER_SECRET_TEST_VALUE"

_RUN_ID = uuid.uuid4()


def _make_gitleaks_finding(
    *,
    rule_id: str = "github-personal-access-token",
    description: str = "detected a GitHub Personal Access Token",
    file: str = "config/settings.py",
    start_line: int = 42,
    match: str = _FAKE_SECRET,
    commit: str = "abc123def456789012345678901234567890abcd",
    fingerprint: str = "abc123:config/settings.py:github-personal-access-token",
) -> dict:
    """Build a realistic Gitleaks JSON finding dict."""
    return {
        "RuleID": rule_id,
        "Description": description,
        "StartLine": start_line,
        "EndLine": start_line,
        "StartColumn": 15,
        "EndColumn": 15 + len(match),
        "Match": match,
        "File": file,
        "Commit": commit,
        "Author": "developer",
        "Email": "dev@example.com",
        "Message": "update config",
        "Date": "2024-01-15T10:30:00Z",
        "Fingerprint": fingerprint,
    }


class TestSeverityInference:
    """Verify severity inference from rule IDs."""

    def test_github_pat_is_high(self) -> None:
        assert _infer_severity("github-personal-access-token") == Severity.HIGH

    def test_private_key_is_critical(self) -> None:
        assert _infer_severity("private-key") == Severity.CRITICAL

    def test_aws_secret_key_is_critical(self) -> None:
        assert _infer_severity("aws-secret-key") == Severity.CRITICAL

    def test_unknown_rule_is_medium(self) -> None:
        assert _infer_severity("some-random-rule") == Severity.MEDIUM


class TestGitleaksParserSecretRedaction:
    """CRITICAL: Verify secrets are never leaked into findings."""

    def test_fake_secret_not_in_finding_title(self) -> None:
        parser = GitleaksResultParser()
        raw = json.dumps([_make_gitleaks_finding()])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        assert len(findings) == 1
        finding = findings[0]
        assert _FAKE_SECRET not in finding.title

    def test_fake_secret_not_in_finding_description(self) -> None:
        parser = GitleaksResultParser()
        raw = json.dumps([_make_gitleaks_finding()])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        finding = findings[0]
        # Description comes from Gitleaks Description field, not the Match
        assert _FAKE_SECRET not in (finding.description or "")

    def test_fake_secret_not_in_finding_location(self) -> None:
        parser = GitleaksResultParser()
        raw = json.dumps([_make_gitleaks_finding()])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        finding = findings[0]
        assert _FAKE_SECRET not in (finding.location or "")

    def test_fake_secret_not_in_any_finding_field(self) -> None:
        """Exhaustive check: the fake secret must not appear in ANY field."""
        parser = GitleaksResultParser()
        raw = json.dumps([_make_gitleaks_finding()])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        finding = findings[0]
        # Check every string field on the finding
        all_text = " ".join(
            str(v)
            for v in [
                finding.title,
                finding.description,
                finding.location,
                finding.package_name,
                finding.installed_version,
                finding.fixed_version,
                finding.vulnerability_id,
                finding.scanner,
                finding.scanner_version,
                *finding.references,
            ]
            if v is not None
        )
        assert _FAKE_SECRET not in all_text, (
            f"CRITICAL SECURITY FAILURE: '{_FAKE_SECRET}' found in normalized finding! "
            f"Full text: {all_text!r}"
        )

    def test_finding_type_is_secret(self) -> None:
        parser = GitleaksResultParser()
        raw = json.dumps([_make_gitleaks_finding()])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        assert findings[0].finding_type == FindingType.SECRET

    def test_scanner_name_and_version(self) -> None:
        parser = GitleaksResultParser(scanner_name="gitleaks", scanner_version="8.18.0")
        raw = json.dumps([_make_gitleaks_finding()])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        assert findings[0].scanner == "gitleaks"
        assert findings[0].scanner_version == "8.18.0"

    def test_location_includes_file_and_line(self) -> None:
        parser = GitleaksResultParser()
        raw = json.dumps([_make_gitleaks_finding(file="src/main.py", start_line=99)])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        assert findings[0].location == "src/main.py:99"

    def test_commit_in_references(self) -> None:
        parser = GitleaksResultParser()
        raw = json.dumps([_make_gitleaks_finding()])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        refs = findings[0].references
        assert any("commit:" in r for r in refs)

    def test_multiple_findings(self) -> None:
        parser = GitleaksResultParser()
        findings_data = [
            _make_gitleaks_finding(rule_id="rule-1", file="a.py"),
            _make_gitleaks_finding(rule_id="rule-2", file="b.py"),
            _make_gitleaks_finding(rule_id="rule-3", file="c.py"),
        ]
        raw = json.dumps(findings_data)
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        assert len(findings) == 3
        assert all(f.finding_type == FindingType.SECRET for f in findings)

    def test_secret_not_in_any_of_multiple_findings(self) -> None:
        """Verify secret redaction across multiple findings."""
        parser = GitleaksResultParser()
        findings_data = [
            _make_gitleaks_finding(
                rule_id="rule-1",
                file="a.py",
                match="SECRET_VALUE_A",
            ),
            _make_gitleaks_finding(
                rule_id="rule-2",
                file="b.py",
                match="SECRET_VALUE_B",
            ),
        ]
        raw = json.dumps(findings_data)
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)

        all_text = json.dumps(
            [
                {
                    "title": f.title,
                    "description": f.description,
                    "location": f.location,
                    "references": f.references,
                }
                for f in findings
            ]
        )
        assert "SECRET_VALUE_A" not in all_text
        assert "SECRET_VALUE_B" not in all_text


class TestGitleaksParserEdgeCases:
    """Test parser resilience with malformed and edge-case inputs."""

    def test_empty_json_array(self) -> None:
        parser = GitleaksResultParser()
        findings = parser.parse("[]", analysis_run_id=_RUN_ID)
        assert findings == []

    def test_empty_string(self) -> None:
        parser = GitleaksResultParser()
        findings = parser.parse("", analysis_run_id=_RUN_ID)
        assert findings == []

    def test_malformed_json(self) -> None:
        parser = GitleaksResultParser()
        findings = parser.parse("not json at all", analysis_run_id=_RUN_ID)
        assert findings == []

    def test_finding_without_rule_id(self) -> None:
        """Findings without RuleID should be skipped."""
        parser = GitleaksResultParser()
        raw = json.dumps([{"Description": "something", "File": "x.py"}])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)
        assert findings == []

    def test_finding_with_missing_optional_fields(self) -> None:
        """Findings with only RuleID should still produce a finding."""
        parser = GitleaksResultParser()
        raw = json.dumps([{"RuleID": "test-rule"}])
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)
        assert len(findings) == 1
        assert findings[0].title == "Secret detected: test-rule"

    def test_dict_wrapped_findings(self) -> None:
        """Gitleaks may wrap in {"findings": [...]}."""
        parser = GitleaksResultParser()
        raw = json.dumps({"findings": [_make_gitleaks_finding()]})
        findings = parser.parse(raw, analysis_run_id=_RUN_ID)
        assert len(findings) == 1

    def test_unknown_json_structure(self) -> None:
        parser = GitleaksResultParser()
        findings = parser.parse('{"unexpected": "data"}', analysis_run_id=_RUN_ID)
        assert findings == []

    def test_none_input_returns_empty(self) -> None:
        """Parser gracefully handles None input (returns empty)."""
        parser = GitleaksResultParser()
        result = parser.parse(None, analysis_run_id=_RUN_ID)  # type: ignore[arg-type]
        assert result == []
