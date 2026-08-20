"""Multi-scanner integration test for Grype + Trivy + Gitleaks + Semgrep.

Verifies that ``ANALYSIS_SCANNERS=trivy,gitleaks,semgrep,grype`` produces
all four providers through the registry, and that existing single-scanner
behavior is preserved.
"""

from app.core.config import Settings
from app.domains.scanners.registry import (
    build_scanner,
    get_registered_scanners,
    parse_scanner_list,
)


class TestScannerRegistryAllFour:
    """Verify the registry includes all four scanners."""

    def test_all_four_registered(self) -> None:
        scanners = get_registered_scanners()
        assert "trivy" in scanners
        assert "gitleaks" in scanners
        assert "semgrep" in scanners
        assert "grype" in scanners

    def test_build_trivy(self) -> None:
        provider = build_scanner("trivy", Settings())
        assert provider.name == "trivy"

    def test_build_gitleaks(self) -> None:
        provider = build_scanner("gitleaks", Settings())
        assert provider.name == "gitleaks"

    def test_build_semgrep(self) -> None:
        provider = build_scanner("semgrep", Settings())
        assert provider.name == "semgrep"

    def test_build_grype(self) -> None:
        provider = build_scanner("grype", Settings())
        assert provider.name == "grype"


class TestFourScannerListParsing:
    """Verify parse_scanner_list for four-scanner config."""

    def test_all_four_scanners(self) -> None:
        result = parse_scanner_list("trivy,gitleaks,semgrep,grype")
        assert result == ["trivy", "gitleaks", "semgrep", "grype"]

    def test_grype_only(self) -> None:
        result = parse_scanner_list("grype")
        assert result == ["grype"]

    def test_deduplication(self) -> None:
        result = parse_scanner_list("trivy,grype,gitleaks,trivy,grype")
        assert result == ["trivy", "grype", "gitleaks"]

    def test_case_insensitive(self) -> None:
        result = parse_scanner_list("Trivy,Gitleaks,Semgrep,Grype")
        assert result == ["trivy", "gitleaks", "semgrep", "grype"]

    def test_whitespace_handling(self) -> None:
        result = parse_scanner_list("  trivy , gitleaks , semgrep , grype  ")
        assert result == ["trivy", "gitleaks", "semgrep", "grype"]

    def test_build_all_configured(self) -> None:
        settings = Settings()
        names = parse_scanner_list("trivy,gitleaks,semgrep,grype")
        providers = [build_scanner(n, settings) for n in names]
        assert len(providers) == 4
        assert [p.name for p in providers] == [
            "trivy",
            "gitleaks",
            "semgrep",
            "grype",
        ]
