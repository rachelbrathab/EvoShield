"""Multi-scanner integration test for Gitleaks + Trivy.

Verifies that ``ANALYSIS_SCANNERS=trivy,gitleaks`` produces both providers
through the registry, and that existing single-scanner behavior is preserved.
"""

from app.core.config import Settings
from app.domains.scanners.registry import (
    build_scanner,
    get_registered_scanners,
    parse_scanner_list,
)


class TestScannerRegistry:
    """Verify the registry includes both scanners."""

    def test_both_scanners_registered(self) -> None:
        scanners = get_registered_scanners()
        assert "trivy" in scanners
        assert "gitleaks" in scanners

    def test_build_trivy(self) -> None:
        provider = build_scanner("trivy", Settings())
        assert provider.name == "trivy"

    def test_build_gitleaks(self) -> None:
        provider = build_scanner("gitleaks", Settings())
        assert provider.name == "gitleaks"


class TestScannerListParsing:
    """Verify parse_scanner_list for multi-scanner config."""

    def test_single_scanner(self) -> None:
        result = parse_scanner_list("trivy")
        assert result == ["trivy"]

    def test_multi_scanner(self) -> None:
        result = parse_scanner_list("trivy,gitleaks")
        assert result == ["trivy", "gitleaks"]

    def test_deduplication(self) -> None:
        result = parse_scanner_list("trivy,gitleaks,trivy")
        assert result == ["trivy", "gitleaks"]

    def test_case_insensitive(self) -> None:
        result = parse_scanner_list("Trivy,Gitleaks")
        assert result == ["trivy", "gitleaks"]

    def test_whitespace_handling(self) -> None:
        result = parse_scanner_list("  trivy , gitleaks  ")
        assert result == ["trivy", "gitleaks"]

    def test_build_all_configured(self) -> None:
        settings = Settings()
        names = parse_scanner_list("trivy,gitleaks")
        providers = [build_scanner(n, settings) for n in names]
        assert len(providers) == 2
        assert providers[0].name == "trivy"
        assert providers[1].name == "gitleaks"
