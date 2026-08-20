"""Tests for the Grype JSON output parser.

Verifies correct normalization of Grype vulnerability matches into
ScannerFinding objects. No raw scanner output should be leaked.
"""

import json
import uuid

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.providers.grype.parser import GrypeResultParser

_RUN_ID = uuid.uuid4()

_PARSER = GrypeResultParser(scanner_name="grype", scanner_version="0.1.0")


def _make_grype_output(matches: list[dict]) -> str:
    """Build a Grype JSON output string from matches."""
    return json.dumps({"matches": matches})


class TestGrypeParserEmpty:
    """Test empty / missing findings."""

    def test_empty_matches(self) -> None:
        output = json.dumps({"matches": []})
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert findings == []

    def test_empty_json_object(self) -> None:
        findings = _PARSER.parse("{}", analysis_run_id=_RUN_ID)
        assert findings == []

    def test_empty_array(self) -> None:
        findings = _PARSER.parse("[]", analysis_run_id=_RUN_ID)
        assert findings == []

    def test_empty_string(self) -> None:
        findings = _PARSER.parse("", analysis_run_id=_RUN_ID)
        assert findings == []

    def test_invalid_json(self) -> None:
        findings = _PARSER.parse("not json at all {{{", analysis_run_id=_RUN_ID)
        assert findings == []

    def test_none_input(self) -> None:
        findings = _PARSER.parse(None, analysis_run_id=_RUN_ID)  # type: ignore[arg-type]
        assert findings == []


class TestGrypeParserSingleFinding:
    """Test parsing a single vulnerability match."""

    def test_single_cve_finding(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {
                        "id": "CVE-2024-1234",
                        "severity": "High",
                        "description": "A test vulnerability",
                        "fix": {"versions": ["1.2.3"]},
                        "urls": ["https://nvd.nist.gov/vuln/detail/CVE-2024-1234"],
                    },
                    "artifact": {
                        "name": "requests",
                        "version": "2.28.0",
                        "type": "python",
                    },
                }
            ]
        )

        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1

        f = findings[0]
        assert f.analysis_run_id == _RUN_ID
        assert f.scanner == "grype"
        assert f.finding_type == FindingType.VULNERABILITY
        assert f.severity == Severity.HIGH
        assert f.vulnerability_id == "CVE-2024-1234"
        assert f.package_name == "requests"
        assert f.installed_version == "2.28.0"
        assert f.fixed_version == "1.2.3"
        assert f.location == "PyPI:requests"
        assert "requests" in f.title
        assert "CVE-2024-1234" in f.title

    def test_critical_severity(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {
                        "id": "CVE-2024-9999",
                        "severity": "Critical",
                    },
                    "artifact": {
                        "name": "lodash",
                        "version": "4.17.20",
                        "type": "npm",
                    },
                }
            ]
        )

        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].severity == Severity.CRITICAL

    def test_low_severity(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {
                        "id": "CVE-2024-0001",
                        "severity": "Low",
                    },
                    "artifact": {
                        "name": "pkg",
                        "version": "1.0.0",
                        "type": "go",
                    },
                }
            ]
        )

        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].severity == Severity.LOW


class TestGrypeParserMultipleFindings:
    """Test parsing multiple vulnerability matches."""

    def test_multiple_findings(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {"id": "CVE-2024-1111", "severity": "High"},
                    "artifact": {"name": "pkg1", "version": "1.0", "type": "npm"},
                },
                {
                    "vulnerability": {"id": "CVE-2024-2222", "severity": "Medium"},
                    "artifact": {"name": "pkg2", "version": "2.0", "type": "python"},
                },
                {
                    "vulnerability": {"id": "CVE-2024-3333", "severity": "Critical"},
                    "artifact": {"name": "pkg3", "version": "3.0", "type": "go"},
                },
            ]
        )

        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 3
        ids = {f.vulnerability_id for f in findings}
        assert ids == {"CVE-2024-1111", "CVE-2024-2222", "CVE-2024-3333"}


class TestGrypeParserMissingFields:
    """Test handling of missing or null fields."""

    def test_missing_vulnerability_id(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {"severity": "High"},
                    "artifact": {"name": "pkg", "version": "1.0"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        # Missing vuln ID → skipped (None return)
        assert findings == []

    def test_missing_artifact(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {"id": "CVE-2024-0001", "severity": "High"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1
        assert findings[0].package_name is None
        assert findings[0].vulnerability_id == "CVE-2024-0001"

    def test_missing_severity(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {"id": "CVE-2024-0001"},
                    "artifact": {"name": "pkg", "version": "1.0"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].severity == Severity.UNKNOWN

    def test_missing_fix(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {"id": "CVE-2024-0001", "severity": "High"},
                    "artifact": {"name": "pkg", "version": "1.0"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].fixed_version is None

    def test_empty_fix_versions(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {
                        "id": "CVE-2024-0001",
                        "severity": "High",
                        "fix": {"versions": []},
                    },
                    "artifact": {"name": "pkg", "version": "1.0"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].fixed_version is None

    def test_no_urls(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {"id": "CVE-2024-0001", "severity": "High"},
                    "artifact": {"name": "pkg", "version": "1.0"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        # Should get a default NVD reference for CVE IDs
        assert any("nvd.nist.gov" in r for r in findings[0].references)


class TestGrypeParserUnexpectedFields:
    """Test resilience to unexpected fields in Grype output."""

    def test_extra_fields_ignored(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {
                        "id": "CVE-2024-0001",
                        "severity": "High",
                        "someNewField": "unexpected",
                        "nested": {"deep": "value"},
                    },
                    "artifact": {
                        "name": "pkg",
                        "version": "1.0",
                        "extra": "data",
                    },
                    "unexpectedTopLevel": "ignored",
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings) == 1
        assert findings[0].vulnerability_id == "CVE-2024-0001"

    def test_malformed_json(self) -> None:
        findings = _PARSER.parse("}{invalid{{json", analysis_run_id=_RUN_ID)
        assert findings == []

    def test_unexpected_root_type(self) -> None:
        findings = _PARSER.parse('"just a string"', analysis_run_id=_RUN_ID)
        assert findings == []

    def test_unexpected_matches_type(self) -> None:
        output = json.dumps({"matches": "not an array"})
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert findings == []


class TestGrypeParserEcosystemMapping:
    """Test ecosystem type mapping."""

    def test_known_ecosystems(self) -> None:
        for eco_type, expected_label in [
            ("python", "PyPI"),
            ("npm", "npm"),
            ("go", "Go"),
            ("cargo", "Rust"),
            ("gem", "RubyGems"),
        ]:
            output = _make_grype_output(
                [
                    {
                        "vulnerability": {"id": "CVE-2024-0001", "severity": "High"},
                        "artifact": {"name": "pkg", "version": "1.0", "type": eco_type},
                    }
                ]
            )
            findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
            assert findings[0].location == f"{expected_label}:pkg"

    def test_unknown_ecosystem(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {"id": "CVE-2024-0001", "severity": "High"},
                    "artifact": {"name": "pkg", "version": "1.0", "type": "custom"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].location == "custom:pkg"


class TestGrypeParserDescription:
    """Test description enrichment."""

    def test_description_with_fix(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {
                        "id": "CVE-2024-0001",
                        "severity": "High",
                        "description": "A vulnerability in the package",
                        "fix": {"versions": ["1.2.3"]},
                    },
                    "artifact": {
                        "name": "pkg",
                        "version": "1.0.0",
                        "type": "python",
                    },
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        desc = findings[0].description or ""
        assert "A vulnerability" in desc
        assert "1.0.0" in desc
        assert "1.2.3" in desc
        assert "PyPI" in desc


class TestGrypeParserReferences:
    """Test reference URL handling."""

    def test_valid_urls_preserved(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {
                        "id": "CVE-2024-0001",
                        "severity": "High",
                        "urls": [
                            "https://nvd.nist.gov/vuln/detail/CVE-2024-0001",
                            "https://github.com/advisories/GHSA-xxxx",
                        ],
                    },
                    "artifact": {"name": "pkg", "version": "1.0"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        assert len(findings[0].references) == 2

    def test_non_http_urls_filtered(self) -> None:
        output = _make_grype_output(
            [
                {
                    "vulnerability": {
                        "id": "CVE-2024-0001",
                        "severity": "High",
                        "urls": [
                            "ftp://example.com/vuln",
                            "file:///local/path",
                            "https://valid.url",
                        ],
                    },
                    "artifact": {"name": "pkg", "version": "1.0"},
                }
            ]
        )
        findings = _PARSER.parse(output, analysis_run_id=_RUN_ID)
        refs = findings[0].references
        assert len(refs) == 1
        assert refs[0] == "https://valid.url"


class TestGrypeParserScannerIdentity:
    """Test that scanner identity is correctly set."""

    def test_custom_scanner_name(self) -> None:
        parser = GrypeResultParser(
            scanner_name="custom-grype",
            scanner_version="2.0.0",
        )
        output = _make_grype_output(
            [
                {
                    "vulnerability": {"id": "CVE-2024-0001", "severity": "High"},
                    "artifact": {"name": "pkg", "version": "1.0"},
                }
            ]
        )
        findings = parser.parse(output, analysis_run_id=_RUN_ID)
        assert findings[0].scanner == "custom-grype"
        assert findings[0].scanner_version == "2.0.0"
