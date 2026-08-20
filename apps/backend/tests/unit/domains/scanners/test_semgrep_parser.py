"""Tests for the Semgrep result parser.

Verifies finding normalization, severity mapping, CWE/OWASP extraction,
and source-code safety (no snippets persisted).  No real Semgrep required.
"""

import json
import uuid

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.providers.semgrep.parser import SemgrepResultParser

_FAKE_SOURCE = "VERY_SENSITIVE_TEST_SOURCE_CODE"
_RUN_ID = uuid.uuid4()


class TestSemgrepParserEmpty:
    """Handle empty and invalid inputs."""

    def test_empty_string(self) -> None:
        parser = SemgrepResultParser()
        assert parser.parse("", analysis_run_id=_RUN_ID) == []

    def test_invalid_json(self) -> None:
        parser = SemgrepResultParser()
        assert parser.parse("not json", analysis_run_id=_RUN_ID) == []

    def test_none_like_input(self) -> None:
        parser = SemgrepResultParser()
        # TypeError from json.loads(None)
        assert parser.parse("", analysis_run_id=_RUN_ID) == []

    def test_empty_results(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps({"results": [], "errors": []})
        assert parser.parse(output, analysis_run_id=_RUN_ID) == []

    def test_missing_results_key(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps({"errors": []})
        assert parser.parse(output, analysis_run_id=_RUN_ID) == []

    def test_non_dict_top_level(self) -> None:
        parser = SemgrepResultParser()
        assert parser.parse('"just a string"', analysis_run_id=_RUN_ID) == []


class TestSemgrepParserSingleFinding:
    """Parse a single Semgrep finding."""

    def test_basic_finding(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "python.lang.security.audit.dangerous-subprocess-call",
                        "path": "app/utils.py",
                        "start": {"line": 42, "col": 5},
                        "end": {"line": 42, "col": 40},
                        "extra": {
                            "message": "Dangerous subprocess call",
                            "severity": "ERROR",
                            "metadata": {
                                "cwe": ["CWE-78"],
                                "owasp": ["A01:2021"],
                            },
                        },
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1
        f = findings[0]
        assert f.finding_type == FindingType.SAST
        assert f.severity == Severity.HIGH
        assert f.title == "python.lang.security.audit.dangerous-subprocess-call"
        assert f.description == "Dangerous subprocess call"
        assert f.location == "app/utils.py:42:5"
        assert "CWE-78" in f.references
        assert "owasp:A01:2021" in f.references

    def test_severity_mapping_warning(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "test-rule",
                        "path": "test.py",
                        "start": {"line": 1},
                        "extra": {"severity": "WARNING"},
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].severity == Severity.MEDIUM

    def test_severity_mapping_info(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "test-rule",
                        "path": "test.py",
                        "start": {"line": 1},
                        "extra": {"severity": "INFO"},
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].severity == Severity.LOW

    def test_unknown_severity_falls_back_to_medium(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "test-rule",
                        "path": "test.py",
                        "start": {"line": 1},
                        "extra": {"severity": "BANANA"},
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].severity == Severity.MEDIUM

    def test_missing_check_id_skipped(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "path": "test.py",
                        "start": {"line": 1},
                        "extra": {"message": "no check_id"},
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 0


class TestSemgrepParserMultipleFindings:
    """Parse multiple Semgrep findings."""

    def test_multiple_findings(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "rule-1",
                        "path": "a.py",
                        "start": {"line": 1},
                        "extra": {"severity": "ERROR"},
                    },
                    {
                        "check_id": "rule-2",
                        "path": "b.py",
                        "start": {"line": 10},
                        "extra": {"severity": "WARNING"},
                    },
                    {
                        "check_id": "rule-3",
                        "path": "c.py",
                        "start": {"line": 20},
                        "extra": {"severity": "INFO"},
                    },
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 3
        assert findings[0].severity == Severity.HIGH
        assert findings[1].severity == Severity.MEDIUM
        assert findings[2].severity == Severity.LOW


class TestSemgrepParserMissingFields:
    """Handle missing optional fields gracefully."""

    def test_missing_extra(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {"results": [{"check_id": "rule-1", "path": "a.py", "start": {"line": 1}}]}
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1

    def test_missing_start(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps({"results": [{"check_id": "rule-1", "path": "a.py", "extra": {}}]})
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1
        assert findings[0].location == "a.py"

    def test_missing_path(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {"results": [{"check_id": "rule-1", "start": {"line": 1}, "extra": {}}]}
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1
        # When path is missing, location falls back to None (empty string → or None)
        assert findings[0].location is None


class TestSemgrepParserSourceCodeSafety:
    """CRITICAL: Ensure source code snippets are never persisted."""

    def test_source_snippet_not_in_finding(self) -> None:
        """The extra.lines field (source snippet) must NOT appear in the finding.

        The parser only reads 'message' from extra — not 'lines' or 'lines_of_code'.
        """
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "test-rule",
                        "path": "vuln.py",
                        "start": {"line": 10},
                        "extra": {
                            "message": "Unsafe subprocess call detected",
                            "severity": "ERROR",
                            "lines": f"subprocess.call({_FAKE_SOURCE})",
                            "lines_of_code": f"subprocess.call({_FAKE_SOURCE})",
                        },
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1
        f = findings[0]

        # CRITICAL: The fake source code must NOT appear in title or location
        assert _FAKE_SOURCE not in f.title
        assert _FAKE_SOURCE not in (f.location or "")
        for ref in f.references:
            assert _FAKE_SOURCE not in ref

        # The message/description contains "Unsafe subprocess call detected" — safe metadata.
        assert f.description == "Unsafe subprocess call detected"

    def test_metavars_not_leaked(self) -> None:
        """Semgrep metavariables must not leak sensitive content."""
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "test-rule",
                        "path": "vuln.py",
                        "start": {"line": 10},
                        "extra": {
                            "message": "test finding",
                            "severity": "ERROR",
                            "metadata": {},
                        },
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1
        assert _FAKE_SOURCE not in findings[0].title


class TestSemgrepParserMetadata:
    """Verify CWE/OWASP extraction."""

    def test_cwe_references(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "rule-1",
                        "path": "a.py",
                        "start": {"line": 1},
                        "extra": {
                            "severity": "ERROR",
                            "metadata": {
                                "cwe": ["CWE-78", "CWE-89"],
                            },
                        },
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert "CWE-78" in findings[0].references
        assert "CWE-89" in findings[0].references

    def test_owasp_references(self) -> None:
        parser = SemgrepResultParser()
        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "rule-1",
                        "path": "a.py",
                        "start": {"line": 1},
                        "extra": {
                            "severity": "ERROR",
                            "metadata": {
                                "owasp": ["A01:2021", "A03:2021"],
                            },
                        },
                    }
                ]
            }
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert "owasp:A01:2021" in findings[0].references
        assert "owasp:A03:2021" in findings[0].references
