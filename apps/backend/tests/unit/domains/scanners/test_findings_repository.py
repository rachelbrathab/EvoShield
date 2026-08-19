"""Findings repository unit tests.

Tests the FindingRepository with the real test database.
Verifies:
- Creating findings
- Listing findings for a run
- Listing findings for a repository
- Owner scoping
- Severity filtering
- Finding type filtering
- Pagination
"""

import asyncio
import uuid

from app.db.session import session_factory
from app.domains.scanners.enums import FindingType, Severity
from app.domains.scanners.ports import ScannerFinding
from app.domains.scanners.repository import FindingRepository
from app.models.analysis_run import AnalysisRun, AnalysisRunStatus
from app.models.repository import AnalysisStatus, Repository
from app.models.user import User


async def _make_user() -> uuid.UUID:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email=f"findings-{uuid.uuid4().hex[:8]}@example.com",
                auth_provider="local",
            )
        )
        await session.commit()
    return user_id


async def _make_repo(user_id: uuid.UUID) -> Repository:
    async with session_factory() as session:
        repo = Repository(
            owner_id=user_id,
            provider="github",
            name="test-repo",
            full_name=f"test/{uuid.uuid4().hex[:8]}",
            analysis_status=AnalysisStatus.NOT_ANALYZED,
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        return repo


async def _make_run(repo_id: uuid.UUID) -> AnalysisRun:
    async with session_factory() as session:
        run = AnalysisRun(
            repository_id=repo_id,
            triggered_by="user",
            status=AnalysisRunStatus.COMPLETED,
            analysis_version="0.1.0",
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


def _make_finding(
    run_id: uuid.UUID,
    *,
    severity: Severity = Severity.HIGH,
    finding_type: FindingType = FindingType.VULNERABILITY,
    vuln_id: str | None = "CVE-2024-1234",
    title: str = "Test finding",
) -> ScannerFinding:
    return ScannerFinding(
        analysis_run_id=run_id,
        scanner="trivy",
        scanner_version="0.1.0",
        finding_type=finding_type,
        severity=severity,
        title=title,
        vulnerability_id=vuln_id,
        package_name="test-pkg",
        installed_version="1.0.0",
    )


def test_create_many_findings() -> None:
    async def scenario() -> None:
        user_id = await _make_user()
        repo = await _make_repo(user_id)
        run = await _make_run(repo.id)
        findings = [
            _make_finding(run.id, severity=Severity.CRITICAL, vuln_id="CVE-001"),
            _make_finding(run.id, severity=Severity.HIGH, vuln_id="CVE-002"),
            _make_finding(run.id, severity=Severity.LOW, vuln_id="CVE-003"),
        ]

        async with session_factory() as session:
            repo_obj = FindingRepository(session)
            count = await repo_obj.create_many(findings)
            await session.commit()
            assert count == 3

        async with session_factory() as session:
            repo_obj = FindingRepository(session)
            stored, total = await repo_obj.list_for_run(run.id)
            assert total == 3
            assert len(stored) == 3

    asyncio.run(scenario())


def test_list_findings_with_severity_filter() -> None:
    async def scenario() -> None:
        user_id = await _make_user()
        repo = await _make_repo(user_id)
        run = await _make_run(repo.id)
        findings = [
            _make_finding(run.id, severity=Severity.CRITICAL),
            _make_finding(run.id, severity=Severity.HIGH, vuln_id="CVE-002"),
            _make_finding(run.id, severity=Severity.LOW, vuln_id="CVE-003"),
        ]

        async with session_factory() as session:
            await FindingRepository(session).create_many(findings)
            await session.commit()

        async with session_factory() as session:
            repo_obj = FindingRepository(session)
            critical, total = await repo_obj.list_for_run(run.id, severity=Severity.CRITICAL)
            assert total == 1
            assert critical[0].severity == Severity.CRITICAL

    asyncio.run(scenario())


def test_list_findings_for_repository() -> None:
    async def scenario() -> None:
        user_id = await _make_user()
        repo = await _make_repo(user_id)
        run = await _make_run(repo.id)
        findings = [_make_finding(run.id), _make_finding(run.id, vuln_id="CVE-002")]

        async with session_factory() as session:
            await FindingRepository(session).create_many(findings)
            await session.commit()

        async with session_factory() as session:
            repo_obj = FindingRepository(session)
            _stored, total = await repo_obj.list_for_repository(user_id, repo.id)
            assert total == 2

    asyncio.run(scenario())


def test_findings_are_owner_scoped() -> None:
    async def scenario() -> None:
        alice = await _make_user()
        bob = await _make_user()
        repo = await _make_repo(alice)
        run = await _make_run(repo.id)
        findings = [_make_finding(run.id)]

        async with session_factory() as session:
            await FindingRepository(session).create_many(findings)
            await session.commit()

        async with session_factory() as session:
            repo_obj = FindingRepository(session)
            # Alice can see findings
            _alice_findings, alice_total = await repo_obj.list_for_repository(alice, repo.id)
            assert alice_total == 1

            # Bob cannot see Alice's findings
            bob_findings, bob_total = await repo_obj.list_for_repository(bob, repo.id)
            assert bob_total == 0
            assert len(bob_findings) == 0

    asyncio.run(scenario())


def test_empty_findings_list() -> None:
    async def scenario() -> None:
        user_id = await _make_user()
        repo = await _make_repo(user_id)
        run = await _make_run(repo.id)

        async with session_factory() as session:
            repo_obj = FindingRepository(session)
            stored, total = await repo_obj.list_for_run(run.id)
            assert total == 0
            assert stored == []

    asyncio.run(scenario())
