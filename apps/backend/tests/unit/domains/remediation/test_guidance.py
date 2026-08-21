"""Tests for deterministic remediation guidance.

Verifies that guidance is correct for each finding type and that
no unsafe information leaks through guidance responses.
"""

from app.domains.remediation.enums import FixAvailability
from app.domains.remediation.guidance import (
    assess_fix_availability,
    get_remediation_guidance,
)


class TestFixAvailability:
    """Test fix availability assessment."""

    def test_secret_not_applicable(self) -> None:
        result = assess_fix_availability(
            finding_type="secret",
            fixed_version=None,
            vulnerability_id=None,
            installed_version=None,
        )
        assert result == FixAvailability.NOT_APPLICABLE

    def test_fixed_version_exists(self) -> None:
        result = assess_fix_availability(
            finding_type="vulnerability",
            fixed_version="4.17.21",
            vulnerability_id="CVE-2021-12345",
            installed_version="4.17.15",
        )
        assert result == FixAvailability.FIX_AVAILABLE

    def test_vuln_no_fix(self) -> None:
        result = assess_fix_availability(
            finding_type="vulnerability",
            fixed_version=None,
            vulnerability_id="CVE-2021-12345",
            installed_version="4.17.15",
        )
        assert result == FixAvailability.NO_KNOWN_FIX

    def test_license_unknown(self) -> None:
        result = assess_fix_availability(
            finding_type="license",
            fixed_version=None,
            vulnerability_id=None,
            installed_version=None,
        )
        assert result == FixAvailability.UNKNOWN

    def test_configuration_unknown(self) -> None:
        result = assess_fix_availability(
            finding_type="configuration",
            fixed_version=None,
            vulnerability_id=None,
            installed_version=None,
        )
        assert result == FixAvailability.UNKNOWN

    def test_no_vuln_id_no_fix_unknown(self) -> None:
        result = assess_fix_availability(
            finding_type="vulnerability",
            fixed_version=None,
            vulnerability_id=None,
            installed_version=None,
        )
        assert result == FixAvailability.UNKNOWN


class TestSecretGuidance:
    """Verify secret guidance never exposes the secret."""

    def test_secret_guidance_safe(self) -> None:
        result = get_remediation_guidance(
            finding_type="secret",
            scanner="gitleaks",
            title="AWS key detected",
            description=None,
            package_name=None,
            installed_version=None,
            fixed_version=None,
            vulnerability_id=None,
            location="config.env",
        )
        # Must contain actionable steps
        assert any("revoke" in s.lower() for s in result["steps"])
        assert any("rotate" in s.lower() for s in result["steps"])
        # Must NOT contain the actual secret
        assert "SUPER_SECRET_TEST_VALUE" not in str(result)
        assert "ghp_" not in str(result)

    def test_secret_guidance_never_exposes_sentinel(self) -> None:
        sentinel = "SUPER_SECRET_TEST_VALUE"
        result = get_remediation_guidance(
            finding_type="secret",
            scanner="gitleaks",
            title=f"Secret detected: {sentinel}",
            description=f"Found {sentinel} in code",
            package_name=None,
            installed_version=None,
            fixed_version=None,
            vulnerability_id=None,
            location="secrets.txt",
        )
        result_str = str(result)
        assert sentinel not in result_str, (
            f"Secret sentinel '{sentinel}' found in guidance response!"
        )


class TestVulnerabilityGuidance:
    """Verify vulnerability guidance for Trivy/Grype findings."""

    def test_with_fix(self) -> None:
        result = get_remediation_guidance(
            finding_type="vulnerability",
            scanner="trivy",
            title="Prototype Pollution in lodash",
            description="A prototype pollution vulnerability",
            package_name="lodash",
            installed_version="4.17.15",
            fixed_version="4.17.21",
            vulnerability_id="CVE-2021-12345",
            location=None,
        )
        assert "lodash" in result["summary"]
        assert "4.17.21" in result["summary"]
        assert "4.17.15" in result["summary"]
        assert "CVE-2021-12345" in result["summary"]
        assert any("upgrade" in s.lower() for s in result["steps"])

    def test_without_fix(self) -> None:
        result = get_remediation_guidance(
            finding_type="vulnerability",
            scanner="grype",
            title="Buffer Overflow",
            description=None,
            package_name="libxml2",
            installed_version="2.9.10",
            fixed_version=None,
            vulnerability_id="CVE-2022-99999",
            location=None,
        )
        assert "libxml2" in result["summary"]
        assert "CVE-2022-99999" in result["summary"]
        # Should not mention a specific upgrade version
        assert (
            "upgrade" not in result["recommendation"].lower()
            or "available" in result["recommendation"].lower()
        )


class TestSASTGuidance:
    """Verify SAST (Semgrep) guidance."""

    def test_sast_guidance(self) -> None:
        result = get_remediation_guidance(
            finding_type="sast",
            scanner="semgrep",
            title="SQL injection vulnerability",
            description="User input in SQL query",
            package_name=None,
            installed_version=None,
            fixed_version=None,
            vulnerability_id=None,
            location="src/db/query.py",
        )
        assert "SQL injection" in result["summary"]
        assert "src/db/query.py" in result["summary"]
        assert len(result["steps"]) >= 3


class TestGenericGuidance:
    """Verify fallback guidance for unknown finding types."""

    def test_unknown_type(self) -> None:
        result = get_remediation_guidance(
            finding_type="unknown_future_type",
            scanner="future_scanner",
            title="Some finding",
            description=None,
            package_name=None,
            installed_version=None,
            fixed_version=None,
            vulnerability_id=None,
            location=None,
        )
        assert len(result["steps"]) >= 1
        assert result["summary"]  # Non-empty
        assert result["recommendation"]  # Non-empty


class TestLicenseGuidance:
    """Verify license guidance."""

    def test_license_guidance(self) -> None:
        result = get_remediation_guidance(
            finding_type="license",
            scanner="trivy",
            title="GPL-3.0 license detected",
            description="GPL-3.0 in dependency tree",
            package_name="gpl-lib",
            installed_version="1.0.0",
            fixed_version=None,
            vulnerability_id=None,
            location=None,
        )
        assert "gpl-lib" in result["summary"]
        assert len(result["steps"]) >= 2
