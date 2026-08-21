"""Tests for the deterministic risk scoring engine.

Verifies scoring weights, bounds, risk levels, aggregation helpers,
and key invariants (more severe findings cannot reduce risk, etc.).
"""

from app.domains.intelligence.scoring import (
    aggregate_by_scanner,
    aggregate_by_type,
    aggregate_severities,
    compute_risk_level,
    compute_risk_score,
    count_secrets,
    count_unfixed_vulns,
)


class TestRiskScoreBounds:
    """Risk score must always be in [0, 100]."""

    def test_zero_findings_is_healthy(self) -> None:
        score = compute_risk_score(
            severity_counts={},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        assert score == 100.0

    def test_score_never_exceeds_100(self) -> None:
        score = compute_risk_score(
            severity_counts={"low": 0},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        assert score <= 100.0

    def test_score_never_below_zero(self) -> None:
        score = compute_risk_score(
            severity_counts={"critical": 100},
            secret_count=100,
            unfixed_vuln_count=100,
        )
        assert score >= 0.0

    def test_many_critical_findings_floor_at_zero(self) -> None:
        score = compute_risk_score(
            severity_counts={"critical": 20},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        assert score == 0.0


class TestRiskScoreWeights:
    """Verify severity weights produce expected scores."""

    def test_single_critical(self) -> None:
        score = compute_risk_score(
            severity_counts={"critical": 1},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        assert score == 75.0  # 100 - 25

    def test_single_high(self) -> None:
        score = compute_risk_score(
            severity_counts={"high": 1},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        assert score == 85.0  # 100 - 15

    def test_single_medium(self) -> None:
        score = compute_risk_score(
            severity_counts={"medium": 1},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        assert score == 92.0  # 100 - 8

    def test_single_low(self) -> None:
        score = compute_risk_score(
            severity_counts={"low": 1},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        assert score == 98.0  # 100 - 2

    def test_mixed_severities(self) -> None:
        score = compute_risk_score(
            severity_counts={
                "critical": 1,
                "high": 2,
                "medium": 3,
                "low": 4,
            },
            secret_count=0,
            unfixed_vuln_count=0,
        )
        # 100 - 25 - 30 - 24 - 8 = 13
        assert score == 13.0


class TestRiskScorePenalties:
    """Secret and unfixed vulnerability penalties."""

    def test_secret_penalty(self) -> None:
        base = compute_risk_score(
            severity_counts={},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        with_secret = compute_risk_score(
            severity_counts={},
            secret_count=1,
            unfixed_vuln_count=0,
        )
        assert base - with_secret == 20.0

    def test_multiple_secrets_same_penalty(self) -> None:
        one = compute_risk_score(
            severity_counts={},
            secret_count=1,
            unfixed_vuln_count=0,
        )
        many = compute_risk_score(
            severity_counts={},
            secret_count=10,
            unfixed_vuln_count=0,
        )
        # Same penalty regardless of count
        assert one == many

    def test_unfixed_vuln_penalty(self) -> None:
        base = compute_risk_score(
            severity_counts={},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        with_fix = compute_risk_score(
            severity_counts={},
            secret_count=0,
            unfixed_vuln_count=3,
        )
        assert base - with_fix == 15.0  # 3 * 5


class TestRiskScoreDeterminism:
    """Score must be deterministic for the same inputs."""

    def test_same_inputs_same_score(self) -> None:
        score1 = compute_risk_score(
            severity_counts={"critical": 2, "high": 3},
            secret_count=1,
            unfixed_vuln_count=2,
        )
        score2 = compute_risk_score(
            severity_counts={"critical": 2, "high": 3},
            secret_count=1,
            unfixed_vuln_count=2,
        )
        assert score1 == score2


class TestRiskLevel:
    """Risk level mapping from score."""

    def test_critical_level(self) -> None:
        assert compute_risk_level(0.0) == "critical"
        assert compute_risk_level(20.0) == "critical"

    def test_high_level(self) -> None:
        assert compute_risk_level(21.0) == "high"
        assert compute_risk_level(40.0) == "high"

    def test_medium_level(self) -> None:
        assert compute_risk_level(41.0) == "medium"
        assert compute_risk_level(60.0) == "medium"

    def test_low_level(self) -> None:
        assert compute_risk_level(61.0) == "low"
        assert compute_risk_level(80.0) == "low"

    def test_healthy_level(self) -> None:
        assert compute_risk_level(81.0) == "healthy"
        assert compute_risk_level(100.0) == "healthy"

    def test_more_severe_findings_worsen_score(self) -> None:
        """Invariant: more severe findings should not improve the score."""
        low_score = compute_risk_score(
            severity_counts={"low": 5},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        critical_score = compute_risk_score(
            severity_counts={"critical": 5},
            secret_count=0,
            unfixed_vuln_count=0,
        )
        assert critical_score < low_score


class TestAggregation:
    """Test finding aggregation helpers."""

    def test_aggregate_severities_empty(self) -> None:
        assert aggregate_severities([]) == {}

    def test_aggregate_severities(self) -> None:
        class FakeFinding:
            def __init__(self, sev: str):
                class _Sev:
                    value = sev

                self.severity = _Sev()

        findings = [
            FakeFinding("critical"),
            FakeFinding("high"),
            FakeFinding("critical"),
            FakeFinding("low"),
        ]
        result = aggregate_severities(findings)
        assert result == {"critical": 2, "high": 1, "low": 1}

    def test_aggregate_by_type(self) -> None:
        class FakeFinding:
            def __init__(self, ftype: str):
                class _Type:
                    value = ftype

                self.finding_type = _Type()

        findings = [
            FakeFinding("vulnerability"),
            FakeFinding("secret"),
            FakeFinding("vulnerability"),
        ]
        result = aggregate_by_type(findings)
        assert result == {"vulnerability": 2, "secret": 1}

    def test_aggregate_by_scanner(self) -> None:
        class FakeFinding:
            def __init__(self, scanner: str):
                self.scanner = scanner

        findings = [
            FakeFinding("trivy"),
            FakeFinding("grype"),
            FakeFinding("trivy"),
        ]
        result = aggregate_by_scanner(findings)
        assert result == {"trivy": 2, "grype": 1}


class TestCountHelpers:
    """Test count_secrets and count_unfixed_vulns."""

    def test_count_secrets_empty(self) -> None:
        assert count_secrets([]) == 0

    def test_count_secrets(self) -> None:
        class FakeFinding:
            def __init__(self, ftype: str):
                class _Type:
                    value = ftype

                self.finding_type = _Type()

        findings = [
            FakeFinding("secret"),
            FakeFinding("vulnerability"),
            FakeFinding("secret"),
        ]
        assert count_secrets(findings) == 2

    def test_count_unfixed_vulns(self) -> None:
        class FakeVuln:
            def __init__(self, vuln_id: str | None, fixed: str | None):
                class _Type:
                    value = "vulnerability"

                self.finding_type = _Type()
                self.vulnerability_id = vuln_id
                self.fixed_version = fixed

        findings = [
            FakeVuln("CVE-1", "1.2.3"),  # fixed
            FakeVuln("CVE-2", None),  # no fix
            FakeVuln(None, "1.0.0"),  # no vuln_id
            FakeVuln("CVE-3", "2.0.0"),  # fixed
        ]
        assert count_unfixed_vulns(findings) == 2
