"""Tests for RemediationService.

Verifies the full remediation intelligence pipeline including:
- Finding status management
- Remediation guidance
- Fix availability
- Prioritization
- Summary metrics
- Owner enforcement
- API endpoint
- Secret/source-code redaction

Uses session_factory() directly, matching the existing test pattern.
"""

import uuid

import pytest

from app.db.session import session_factory
from app.domains.remediation.enums import FixAvailability
from app.domains.remediation.service import RemediationService
from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.finding import Finding, FindingType, Severity
from app.models.repository import AnalysisStatus, Repository
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
) -> AnalysisRun:
    run = AnalysisRun(
        repository_id=repository_id,
        status=AnalysisRunStatus.COMPLETED,
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
    description: str | None = None,
    package_name: str | None = None,
    installed_version: str | None = None,
    fixed_version: str | None = None,
    vulnerability_id: str | None = None,
    location: str | None = None,
) -> Finding:
    finding = Finding(
        analysis_run_id=analysis_run_id,
        scanner=scanner,
        scanner_version="0.1.0",
        finding_type=finding_type,
        severity=severity,
        title=title,
        description=description,
        package_name=package_name,
        installed_version=installed_version,
        fixed_version=fixed_version,
        vulnerability_id=vulnerability_id,
        location=location,
    )
    session.add(finding)
    await session.flush()
    return finding


class TestRemediationOwnership:
    """Ownership enforcement — cross-user access must be denied."""

    @pytest.mark.asyncio
    async def test_owner_can_access(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id, severity=Severity.HIGH)
            await session.commit()

            service = RemediationService(session)
            result = await service.get_remediation(user.id, run.id)
            assert result.analysis_id == str(run.id)

    @pytest.mark.asyncio
    async def test_cross_user_denied(self) -> None:
        async with session_factory() as session:
            owner = await _create_user(session)
            other = await _create_user(session)
            repo = await _create_repo(session, owner.id)
            run = await _create_analysis(session, repo.id)
            await session.commit()

            from app.core.exceptions import NotFoundError

            service = RemediationService(session)
            with pytest.raises(NotFoundError):
                await service.get_remediation(other.id, run.id)


class TestRemediationStatus:
    """Test finding status management."""

    @pytest.mark.asyncio
    async def test_default_status_is_open(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id)
            await session.commit()

            service = RemediationService(session)
            result = await service.get_remediation(user.id, run.id)
            assert result.summary.open_count == 1
            assert result.findings[0].status == "open"

    @pytest.mark.asyncio
    async def test_acknowledge_finding(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            f = await _create_finding(session, run.id)
            await session.commit()

            from app.domains.remediation.schemas import RemediationStatusUpdate

            service = RemediationService(session)
            result = await service.update_status(
                user.id,
                run.id,
                f.id,
                RemediationStatusUpdate(
                    status="acknowledged",
                    note="Will fix in next sprint",
                ),
            )
            await session.commit()
            assert result.status == "acknowledged"

    @pytest.mark.asyncio
    async def test_resolve_finding(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            f = await _create_finding(session, run.id)
            await session.commit()

            from app.domains.remediation.schemas import RemediationStatusUpdate

            service = RemediationService(session)
            result = await service.update_status(
                user.id,
                run.id,
                f.id,
                RemediationStatusUpdate(status="resolved"),
            )
            await session.commit()
            assert result.status == "resolved"

    @pytest.mark.asyncio
    async def test_false_positive(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            f = await _create_finding(session, run.id)
            await session.commit()

            from app.domains.remediation.schemas import RemediationStatusUpdate

            service = RemediationService(session)
            result = await service.update_status(
                user.id,
                run.id,
                f.id,
                RemediationStatusUpdate(status="false_positive"),
            )
            await session.commit()
            assert result.status == "false_positive"

    @pytest.mark.asyncio
    async def test_invalid_status_rejected(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            f = await _create_finding(session, run.id)
            await session.commit()

            from app.core.exceptions import NotFoundError
            from app.domains.remediation.schemas import RemediationStatusUpdate

            service = RemediationService(session)
            with pytest.raises(NotFoundError):
                await service.update_status(
                    user.id,
                    run.id,
                    f.id,
                    RemediationStatusUpdate(status="invalid_status"),
                )


class TestRemediationGuidance:
    """Verify guidance is correct per finding type."""

    @pytest.mark.asyncio
    async def test_secret_guidance(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.SECRET,
                title="AWS key detected",
            )
            await session.commit()

            service = RemediationService(session)
            result = await service.get_remediation(user.id, run.id)
            secret_finding = result.findings[0]
            assert "secret" in secret_finding.guidance.summary.lower()
            assert secret_finding.fix_availability == FixAvailability.NOT_APPLICABLE.value

    @pytest.mark.asyncio
    async def test_vuln_with_fix_guidance(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.VULNERABILITY,
                package_name="lodash",
                installed_version="4.17.15",
                fixed_version="4.17.21",
                vulnerability_id="CVE-2021-12345",
            )
            await session.commit()

            service = RemediationService(session)
            result = await service.get_remediation(user.id, run.id)
            vuln_finding = result.findings[0]
            assert "lodash" in vuln_finding.guidance.summary
            assert vuln_finding.fix_availability == FixAvailability.FIX_AVAILABLE.value

    @pytest.mark.asyncio
    async def test_sast_guidance(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.SAST,
                title="SQL injection",
                location="src/db.py",
            )
            await session.commit()

            service = RemediationService(session)
            result = await service.get_remediation(user.id, run.id)
            assert result.findings[0].guidance.summary
            assert len(result.findings[0].guidance.steps) >= 3


class TestRemediationSummary:
    """Verify summary metrics."""

    @pytest.mark.asyncio
    async def test_summary_counts(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(
                session,
                run.id,
                severity=Severity.CRITICAL,
                fixed_version="2.0.0",
                vulnerability_id="CVE-1",
            )
            await _create_finding(
                session,
                run.id,
                severity=Severity.HIGH,
            )
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.SECRET,
                severity=Severity.CRITICAL,
            )
            await session.commit()

            service = RemediationService(session)
            result = await service.get_remediation(user.id, run.id)

            assert result.summary.total_findings == 3
            assert result.summary.open_count == 3
            assert result.summary.resolved_count == 0
            assert result.summary.remediation_rate == 0.0
            assert result.summary.fixable_count == 1  # Only the vuln with fix

    @pytest.mark.asyncio
    async def test_remediation_rate_after_resolve(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            f1 = await _create_finding(session, run.id, severity=Severity.HIGH)
            await _create_finding(session, run.id, severity=Severity.LOW)
            await session.commit()

            from app.domains.remediation.schemas import RemediationStatusUpdate

            service = RemediationService(session)
            await service.update_status(
                user.id,
                run.id,
                f1.id,
                RemediationStatusUpdate(status="resolved"),
            )
            await session.commit()

            result = await service.get_remediation(user.id, run.id)
            assert result.summary.resolved_count == 1
            assert result.summary.remediation_rate == 50.0

    @pytest.mark.asyncio
    async def test_empty_findings_summary(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await session.commit()

            service = RemediationService(session)
            result = await service.get_remediation(user.id, run.id)
            assert result.summary.total_findings == 0
            assert result.summary.remediation_rate == 0.0


class TestRemediationPrioritization:
    """Verify finding prioritization."""

    @pytest.mark.asyncio
    async def test_critical_open_before_high_open(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(session, run.id, severity=Severity.HIGH, title="High")
            await _create_finding(session, run.id, severity=Severity.CRITICAL, title="Critical")
            await session.commit()

            service = RemediationService(session)
            result = await service.get_remediation(user.id, run.id)
            assert result.findings[0].severity == "critical"
            assert result.findings[1].severity == "high"

    @pytest.mark.asyncio
    async def test_resolved_after_open(self) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            f1 = await _create_finding(
                session, run.id, severity=Severity.CRITICAL, title="Critical"
            )
            await _create_finding(session, run.id, severity=Severity.LOW, title="Low")
            await session.commit()

            from app.domains.remediation.schemas import RemediationStatusUpdate

            service = RemediationService(session)
            await service.update_status(
                user.id,
                run.id,
                f1.id,
                RemediationStatusUpdate(status="resolved"),
            )
            await session.commit()

            result = await service.get_remediation(user.id, run.id)
            # Resolved critical should come after open low
            assert result.findings[0].status == "open"
            assert result.findings[-1].status == "resolved"


class TestRemediationAPIEndpoint:
    """Test the API endpoints through the test client."""

    @pytest.mark.asyncio
    async def test_remediation_endpoint(self, client) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            await _create_finding(
                session,
                run.id,
                severity=Severity.HIGH,
                package_name="lodash",
                fixed_version="4.17.21",
                vulnerability_id="CVE-2021-12345",
            )
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
            f"/api/v1/analysis/{run_id}/remediation",
            cookies={settings.session_cookie_name: token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["analysis_id"] == str(run_id)
        assert data["summary"]["total_findings"] == 1
        assert data["summary"]["open_count"] == 1
        assert len(data["findings"]) == 1

    @pytest.mark.asyncio
    async def test_status_update_endpoint(self, client) -> None:
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            f = await _create_finding(session, run.id)
            await session.commit()

            user_id = user.id
            run_id = run.id
            finding_id = f.id

        import jwt

        from app.core.config import get_settings

        settings = get_settings()
        token = jwt.encode(
            {"sub": str(user_id), "exp": 9999999999},
            settings.session_jwt_secret,
            algorithm="HS256",
        )

        response = client.patch(
            f"/api/v1/analysis/{run_id}/findings/{finding_id}/status",
            json={"status": "acknowledged", "note": "Investigating"},
            cookies={settings.session_cookie_name: token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"

    @pytest.mark.asyncio
    async def test_secret_not_in_remediation_response(self, client) -> None:
        """CRITICAL SECURITY TEST: Ensure remediation guidance never adds secrets.

        The remediation service's security guarantee is that it never ADDS
        secret values to its responses. The Gitleaks parser is responsible for
        never storing actual secret values in Finding fields (title, description).
        """
        async with session_factory() as session:
            user = await _create_user(session)
            repo = await _create_repo(session, user.id)
            run = await _create_analysis(session, repo.id)
            # Properly redacted Gitleaks finding — title does NOT contain the secret
            await _create_finding(
                session,
                run.id,
                finding_type=FindingType.SECRET,
                title="AWS key detected in config.env",
                location="config.env",
            )
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
            f"/api/v1/analysis/{run_id}/remediation",
            cookies={settings.session_cookie_name: token},
        )
        assert response.status_code == 200
        data = response.json()

        # The remediation guidance must never contain secret-like patterns
        guidance = data["findings"][0]["guidance"]
        assert guidance["summary"]  # Non-empty
        assert "revoke" in guidance["recommendation"].lower()
        assert len(guidance["steps"]) >= 4

        # Verify the guidance itself does not leak sensitive values
        response_str = str(data)
        assert "ghp_" not in response_str
        assert "sk_live_" not in response_str
        assert "AKIA" not in response_str
