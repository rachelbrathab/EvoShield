"""Tests for the intelligence service.

Verifies the full intelligence computation pipeline including
ownership enforcement, trend calculation, scanner coverage,
risk factors, and prioritization.

Uses session_factory() directly, matching the existing test pattern.
"""

import uuid

import pytest

from app.db.session import session_factory
from app.domains.intelligence.service import IntelligenceService
from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.finding import Finding, FindingType, Severity
from app.models.repository import AnalysisStatus, Repository
from app.models.scanner_run import ScannerRun, ScannerRunStatus
from app.models.user import User


async def _create_user(session) -> User:
    user = User(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        auth_provider="local",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_repo(session, owner_id: uuid.UUID) -> Repository:
    repo = Repository(
        owner_id=owner_id,
        name="test-repo",
        full_name=f"test-{uuid.uuid4().hex[:8]}/test-repo",
        analysis_status=AnalysisStatus.ANALYZED,
    )
    session.add(repo)
    await session.flush()
    return repo


async def _create_analysis(
    session,
    repository_id: uuid.UUID,
    *,
    status: AnalysisRunStatus = AnalysisRunStatus.COMPLETED,
) -> AnalysisRun:
    run = AnalysisRun(
        repository_id=repository_id,
        status=status,
        triggered_by="user",
        analysis_version="0.1.0",
    )
    session.add(run)
    await session.flush()
    return run


async def _create_finding(
    session,
    analysis_run_id: uuid.UUID,
    *,
    scanner: str = "trivy",
    finding_type: FindingType = FindingType.VULNERABILITY,
    severity: Severity = Severity.HIGH,
    title: str = "Test finding",
    vulnerability_id: str | None = None,
    fixed_version: str | None = None,
) -> Finding:
    finding = Finding(
        analysis_run_id=analysis_run_id,
        scanner=scanner,
        scanner_version="0.1.0",
        finding_type=finding_type,
        severity=severity,
        title=title,
        vulnerability_id=vulnerability_id,
        fixed_version=fixed_version,
    )
    session.add(finding)
    await session.flush()
    return finding


async def _create_scanner_run(
    session,
    analysis_run_id: uuid.UUID,
    *,
    scanner_name: str = "trivy",
    status: ScannerRunStatus = ScannerRunStatus.COMPLETED,
    finding_count: int | None = 0,
) -> ScannerRun:
    sr = ScannerRun(
        analysis_run_id=analysis_run_id,
        scanner_name=scanner_name,
        scanner_version="0.1.0",
        status=status,
        finding_count=finding_count,
    )
    session.add(sr)
    await session.flush()
    return sr


class TestIntelligenceOwnership:
    """Ownership enforcement — cross-user access must be denied."""

    @pytest.mark.asyncio
    async def test_owner_can_access(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id, severity=Severity.HIGH)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)
            assert intel.repository_id == str(repo.id)
            assert intel.analysis_id == str(run.id)

    @pytest.mark.asyncio
    async def test_cross_user_denied(self) -> None:
        async with session_factory() as session:
            owner = await _create_user(session)
            other = await _create_user(session)
            repo = await _create_repo(session, owner.id)
            run = await _create_analysis(session, repo.id)
            await _create_scanner_run(session, run.id)
            await session.commit()

            from app.core.exceptions import NotFoundError

            service = IntelligenceService(session)
            with pytest.raises(NotFoundError):
                await service.get_intelligence(other.id, run.id)


class TestIntelligenceAggregation:
    """Verify finding aggregation in the intelligence response."""

    @pytest.mark.asyncio
    async def test_severity_counts(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id, severity=Severity.CRITICAL)
            await _create_finding(session, run.id, severity=Severity.CRITICAL)
            await _create_finding(session, run.id, severity=Severity.HIGH)
            await _create_finding(session, run.id, severity=Severity.LOW)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.total_findings == 4
            assert intel.severity_counts.critical == 2
            assert intel.severity_counts.high == 1
            assert intel.severity_counts.low == 1
            assert intel.severity_counts.medium == 0

    @pytest.mark.asyncio
    async def test_finding_type_counts(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.VULNERABILITY,
            )
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.VULNERABILITY,
            )
            await _create_finding(session, run.id, finding_type=FindingType.SECRET)
            await _create_finding(session, run.id, finding_type=FindingType.SAST)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.finding_type_counts.vulnerability == 2
            assert intel.finding_type_counts.secret == 1
            assert intel.finding_type_counts.sast == 1

    @pytest.mark.asyncio
    async def test_scanner_counts(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id, scanner="trivy")
            await _create_finding(session, run.id, scanner="trivy")
            await _create_finding(session, run.id, scanner="gitleaks")
            await _create_scanner_run(session, run.id)
            await _create_scanner_run(session, run.id, scanner_name="gitleaks")
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.scanner_counts.trivy == 2
            assert intel.scanner_counts.gitleaks == 1


class TestIntelligenceRiskScore:
    """Verify risk score computation in the full service."""

    @pytest.mark.asyncio
    async def test_no_findings_is_healthy(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.risk_score == 100.0
            assert intel.risk_level == "healthy"

    @pytest.mark.asyncio
    async def test_critical_findings_lower_score(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            for _ in range(5):
                await _create_finding(session, run.id, severity=Severity.CRITICAL)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.risk_score < 100.0
            assert intel.risk_level in ("critical", "high", "medium")


class TestIntelligenceRiskFactors:
    """Verify risk factors are generated correctly."""

    @pytest.mark.asyncio
    async def test_secret_generates_factor(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id, finding_type=FindingType.SECRET)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            categories = [f.category for f in intel.risk_factors]
            assert "secrets" in categories

    @pytest.mark.asyncio
    async def test_no_findings_no_factors(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.risk_factors == []


class TestIntelligencePrioritization:
    """Verify finding prioritization."""

    @pytest.mark.asyncio
    async def test_critical_before_high(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(
                session,
                run.id,
                severity=Severity.HIGH,
                title="High one",
            )
            await _create_finding(
                session,
                run.id,
                severity=Severity.CRITICAL,
                title="Critical one",
            )
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert len(intel.top_findings) == 2
            assert intel.top_findings[0].severity == "critical"
            assert intel.top_findings[1].severity == "high"

    @pytest.mark.asyncio
    async def test_secret_before_vuln(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.VULNERABILITY,
                severity=Severity.CRITICAL,
                title="Vuln",
            )
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.SECRET,
                severity=Severity.CRITICAL,
                title="Secret",
            )
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.top_findings[0].finding_type == "secret"
            assert intel.top_findings[1].finding_type == "vulnerability"


class TestIntelligenceTrend:
    """Verify trend calculation against previous analysis."""

    @pytest.mark.asyncio
    async def test_no_previous_analysis(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.trend.has_previous is False
            assert intel.trend.trend is None

    @pytest.mark.asyncio
    async def test_improving_trend(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)

            prev = await _create_analysis(session, repo.id)
            for _ in range(5):
                await _create_finding(session, prev.id)

            current = await _create_analysis(session, repo.id)
            for _ in range(3):
                await _create_finding(session, current.id)
            await _create_scanner_run(session, current.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, current.id)

            assert intel.trend.has_previous is True
            assert intel.trend.trend == "improving"
            assert intel.trend.finding_delta == -2

    @pytest.mark.asyncio
    async def test_worsening_trend(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)

            prev = await _create_analysis(session, repo.id)
            for _ in range(2):
                await _create_finding(session, prev.id)

            current = await _create_analysis(session, repo.id)
            for _ in range(5):
                await _create_finding(session, current.id)
            await _create_scanner_run(session, current.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, current.id)

            assert intel.trend.trend == "worsening"
            assert intel.trend.finding_delta == 3

    @pytest.mark.asyncio
    async def test_unchanged_trend(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)

            prev = await _create_analysis(session, repo.id)
            for _ in range(3):
                await _create_finding(session, prev.id)

            current = await _create_analysis(session, repo.id)
            for _ in range(3):
                await _create_finding(session, current.id)
            await _create_scanner_run(session, current.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, current.id)

            assert intel.trend.trend == "unchanged"
            assert intel.trend.finding_delta == 0


class TestIntelligenceScannerCoverage:
    """Verify scanner coverage calculation."""

    @pytest.mark.asyncio
    async def test_all_completed(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_scanner_run(session, run.id)
            await _create_scanner_run(session, run.id, scanner_name="gitleaks")
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            cov = intel.scanner_coverage
            assert cov.total_scanners == 2
            assert cov.completed_scanners == 2
            assert cov.failed_scanners == 0
            assert cov.coverage_percentage == 100.0

    @pytest.mark.asyncio
    async def test_one_failed(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_scanner_run(session, run.id)
            await _create_scanner_run(
                session,
                run.id,
                scanner_name="gitleaks",
                status=ScannerRunStatus.FAILED,
            )
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            cov = intel.scanner_coverage
            assert cov.total_scanners == 2
            assert cov.completed_scanners == 1
            assert cov.failed_scanners == 1
            assert cov.coverage_percentage == 50.0

    @pytest.mark.asyncio
    async def test_no_scanner_runs(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert intel.scanner_coverage.total_scanners == 0
            assert intel.scanner_coverage.coverage_percentage == 0.0


class TestIntelligenceSummary:
    """Verify summary generation."""

    @pytest.mark.asyncio
    async def test_healthy_summary(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_scanner_run(session, run.id)
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert "good security posture" in intel.summary.lower()
            assert "no security findings" in intel.summary.lower()

    @pytest.mark.asyncio
    async def test_failed_scanner_in_summary(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_scanner_run(
                session,
                run.id,
                scanner_name="trivy",
                status=ScannerRunStatus.FAILED,
            )
            await session.commit()

            service = IntelligenceService(session)
            intel = await service.get_intelligence(user.id, run.id)

            assert "failed" in intel.summary.lower()
            assert "incomplete" in intel.summary.lower()


class TestIntelligenceAPIEndpoint:
    """Test the API endpoint through the test client."""

    @pytest.mark.asyncio
    async def test_intelligence_endpoint(self, client) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id, severity=Severity.HIGH)
            await _create_scanner_run(session, run.id)
            await session.commit()

            user_id = user.id
            run_id = run.id

        import jwt

        from app.core.config import get_settings

        settings = get_settings()
        token = jwt.encode(
            {"sub": str(user_id), "exp": 9999999999},
            settings.session_jwt_secret,
            algorithm="HS256",
        )

        response = client.get(
            f"/api/v1/analysis/{run_id}/intelligence",
            cookies={settings.session_cookie_name: token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["analysis_id"] == str(run_id)
        assert data["risk_score"] == 85.0
        assert data["risk_level"] == "healthy"
        assert data["total_findings"] == 1
