"""Trivy JSON parser unit tests.

Tests the TrivyResultParser's ability to convert raw Trivy JSON output
into normalized ScannerFinding objects.  No real Trivy binary is needed.
"""

import json
import uuid

from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.providers.trivy.parser import TrivyResultParser


def _make_parser() -> TrivyResultParser:
    return TrivyResultParser(scanner_name="trivy", scanner_version="0.1.0")


def _trivy_output(vulnerabilities: list[dict] | None = None) -> str:
    """Build a minimal Trivy JSON output."""
    return json.dumps(
        {
            "SchemaVersion": "2",
            "Results": [
                {
                    "Target": "requirements.txt",
                    "Class": "lang-pkgs",
                    "Type": "python",
                    "Vulnerabilities": vulnerabilities or [],
                }
            ],
        }
    )


def _vuln(
    *,
    vuln_id: str = "CVE-2024-1234",
    severity: str = "HIGH",
    title: str = "Test vulnerability",
    pkg: str = "requests",
    installed: str = "2.28.0",
    fixed: str = "2.31.0",
    description: str = "A test vulnerability.",
    primary_url: str | None = "https://nvd.nist.gov/vuln/detail/CVE-2024-1234",
) -> dict:
    return {
        "VulnerabilityID": vuln_id,
        "Severity": severity,
        "Title": title,
        "PkgName": pkg,
        "InstalledVersion": installed,
        "FixedVersion": fixed,
        "Description": description,
        "PrimaryURL": primary_url,
    }


class TestTrivyResultParser:
    """Test the Trivy JSON output parser."""

    def test_empty_output_returns_no_findings(self) -> None:
        parser = _make_parser()
        findings = parser.parse("{}", analysis_run_id=uuid.uuid4())
        assert findings == []

    def test_empty_results_returns_no_findings(self) -> None:
        parser = _make_parser()
        output = json.dumps({"Results": []})
        findings = parser.parse(output, analysis_run_id=uuid.uuid4())
        assert findings == []

    def test_no_vulnerabilities_returns_no_findings(self) -> None:
        parser = _make_parser()
        output = _trivy_output(vulnerabilities=[])
        findings = parser.parse(output, analysis_run_id=uuid.uuid4())
        assert findings == []

    def test_single_vulnerability_parsed(self) -> None:
        parser = _make_parser()
        run_id = uuid.uuid4()
        output = _trivy_output(vulnerabilities=[_vuln()])
        findings = parser.parse(output, analysis_run_id=run_id)

        assert len(findings) == 1
        f = findings[0]
        assert f.analysis_run_id == run_id
        assert f.scanner == "trivy"
        assert f.scanner_version == "0.1.0"
        assert f.finding_type == FindingType.VULNERABILITY
        assert f.severity == Severity.HIGH
        assert f.title == "Test vulnerability"
        assert f.vulnerability_id == "CVE-2024-1234"
        assert f.package_name == "requests"
        assert f.installed_version == "2.28.0"
        assert f.fixed_version == "2.31.0"
        assert f.description == "A test vulnerability."
        assert "https://nvd.nist.gov/vuln/detail/CVE-2024-1234" in f.references

    def test_severity_mapping(self) -> None:
        parser = _make_parser()
        run_id = uuid.uuid4()
        for sev_str, expected in [
            ("CRITICAL", Severity.CRITICAL),
            ("HIGH", Severity.HIGH),
            ("MEDIUM", Severity.MEDIUM),
            ("LOW", Severity.LOW),
            ("UNKNOWN", Severity.UNKNOWN),
            ("", Severity.UNKNOWN),
        ]:
            output = _trivy_output(vulnerabilities=[_vuln(severity=sev_str)])
            findings = parser.parse(output, analysis_run_id=run_id)
            assert len(findings) == 1
            assert findings[0].severity == expected, f"severity={sev_str}"

    def test_missing_vuln_id_skips_entry(self) -> None:
        parser = _make_parser()
        output = _trivy_output(vulnerabilities=[{"Severity": "HIGH"}])
        findings = parser.parse(output, analysis_run_id=uuid.uuid4())
        assert findings == []

    def test_missing_optional_fields_handled(self) -> None:
        parser = _make_parser()
        vuln = {
            "VulnerabilityID": "CVE-2024-9999",
            "Severity": "LOW",
        }
        output = _trivy_output(vulnerabilities=[vuln])
        findings = parser.parse(output, analysis_run_id=uuid.uuid4())
        assert len(findings) == 1
        f = findings[0]
        assert f.package_name is None
        assert f.installed_version is None
        assert f.fixed_version is None
        assert f.description is None
        assert f.references == []

    def test_multiple_results_parsed(self) -> None:
        parser = _make_parser()
        output = json.dumps(
            {
                "Results": [
                    {
                        "Target": "requirements.txt",
                        "Vulnerabilities": [_vuln(vuln_id="CVE-2024-0001")],
                    },
                    {
                        "Target": "package.json",
                        "Vulnerabilities": [_vuln(vuln_id="CVE-2024-0002", pkg="lodash")],
                    },
                ],
            }
        )
        findings = parser.parse(output, analysis_run_id=uuid.uuid4())
        assert len(findings) == 2
        ids = {f.vulnerability_id for f in findings}
        assert ids == {"CVE-2024-0001", "CVE-2024-0002"}

    def test_invalid_json_returns_empty(self) -> None:
        parser = _make_parser()
        findings = parser.parse("not json at all", analysis_run_id=uuid.uuid4())
        assert findings == []

    def test_references_deduplicated(self) -> None:
        parser = _make_parser()
        vuln = _vuln(primary_url="https://example.com")
        vuln["References"] = ["https://example.com", "https://other.com"]
        output = _trivy_output(vulnerabilities=[vuln])
        findings = parser.parse(output, analysis_run_id=uuid.uuid4())
        assert len(findings) == 1
        assert findings[0].references.count("https://example.com") == 1
        assert "https://other.com" in findings[0].references

    def test_title_truncated_to_512_chars(self) -> None:
        parser = _make_parser()
        long_title = "A" * 600
        output = _trivy_output(vulnerabilities=[_vuln(title=long_title)])
        findings = parser.parse(output, analysis_run_id=uuid.uuid4())
        assert len(findings) == 1
        assert len(findings[0].title) == 512
