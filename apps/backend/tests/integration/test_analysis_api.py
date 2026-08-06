"""Integration tests for the analysis API (Sprint 4A).

The `get_repository_service` dependency is overridden with a fake GitHub
client (no network) so a repository can be imported, and
`get_analysis_orchestrator` is overridden with an orchestrator configured for
tests: zero queue hold, a fake provider with a controllable delay/failure,
and a short timeout. The full HTTP → service → orchestrator → DB path runs in
one process.
"""

import time
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_analysis_orchestrator, get_repository_service
from app.core.exceptions import NotFoundError
from app.db.session import session_factory
from app.domains.analysis.orchestrator import AnalysisOrchestrator
from app.domains.analysis.providers.fake import FakeAnalysisProvider
from app.domains.github.ports import GitHubRepoData
from app.domains.github.service import RepositoryService
from app.main import app

REGISTER_PAYLOAD = {
    "email": "analysis-admin@example.com",
    "password": "correct-horse-battery",
    "full_name": "Analysis Admin",
}


def _repo_data(full_name: str) -> GitHubRepoData:
    return GitHubRepoData(
        provider_repo_id="1296269",
        name=full_name.split("/")[-1],
        full_name=full_name,
        html_url=f"https://github.com/{full_name}",
        description=f"Repo {full_name}",
        private=False,
        language="Python",
        default_branch="main",
        stars=42,
        forks=7,
        open_issues=3,
        topics=("demo",),
        license_spdx="MIT",
        size_kb=185,
        archived=False,
        disabled=False,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
        pushed_at=datetime(2024, 3, 1, tzinfo=UTC),
    )


class FakeGitHubClient:
    """Minimal GitHubRepoProvider for imports — no network."""

    def __init__(self) -> None:
        self.repos: dict[str, GitHubRepoData] = {}

    async def get_repository(self, full_name: str) -> GitHubRepoData:
        try:
            return self.repos[full_name]
        except KeyError:
            raise NotFoundError("This repository does not exist on GitHub.") from None

    async def list_user_repositories(
        self, *, page: int = 1, per_page: int = 30, query: str | None = None
    ) -> list[GitHubRepoData]:
        return list(self.repos.values())


class FakeTokenProvider:
    async def get_access_token(self, user_id: uuid.UUID, provider: str = "github") -> str | None:
        return "ghp_test"


_active_github = FakeGitHubClient()

# Orchestrator configuration, swapped per test.
_cfg: dict = {"hold": 0.0, "delay": 0.0, "fail": False, "timeout": 30.0}


async def _override_orchestrator() -> AsyncIterator[AnalysisOrchestrator]:
    async with session_factory() as session:
        yield AnalysisOrchestrator(
            session=session,
            session_factory=session_factory,
            provider=FakeAnalysisProvider(
                delay_seconds=_cfg["delay"],
                fail=_cfg["fail"],
            ),
            queued_hold_seconds=_cfg["hold"],
            timeout_seconds=_cfg["timeout"],
        )


async def _override_repository_service() -> AsyncIterator[RepositoryService]:
    async with session_factory() as session:
        yield RepositoryService(
            session=session,
            token_provider=FakeTokenProvider(),
            client_factory=lambda access_token: _active_github,
        )


@pytest.fixture(autouse=True)
def _overrides() -> Iterator[None]:
    _active_github.repos.clear()
    _cfg.update(hold=0.0, delay=0.0, fail=False, timeout=30.0)
    app.dependency_overrides[get_analysis_orchestrator] = _override_orchestrator
    app.dependency_overrides[get_repository_service] = _override_repository_service
    yield
    app.dependency_overrides.pop(get_analysis_orchestrator, None)
    app.dependency_overrides.pop(get_repository_service, None)


def _register(client: TestClient, **overrides: str) -> None:
    payload = {**REGISTER_PAYLOAD, **overrides}
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text


def _import(client: TestClient, full_name: str) -> dict:
    response = client.post("/api/v1/repositories/import", json={"full_name": full_name})
    assert response.status_code == 201, response.text
    return response.json()["repository"]


def _wait_for_status(
    client: TestClient, run_id: str, expected: str, max_wait: float = 10.0
) -> dict:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/analysis/{run_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        if body["status"] == expected:
            return body
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} never reached {expected!r}")


# ── Auth gating ─────────────────────────────────────────────────────────
def test_analysis_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/analysis").status_code == 401
    assert client.get(f"/api/v1/analysis/{uuid.uuid4()}").status_code == 401
    assert client.post(f"/api/v1/analysis/{uuid.uuid4()}/cancel").status_code == 401
    assert client.delete(f"/api/v1/analysis/{uuid.uuid4()}").status_code == 401
    assert client.post(f"/api/v1/repositories/{uuid.uuid4()}/analysis").status_code == 401


# ── Happy path: QUEUED → RUNNING → COMPLETED ────────────────────────────
def test_start_run_completes_and_updates_repository(client: TestClient) -> None:
    _register(client)
    _active_github.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World")

    response = client.post(f"/api/v1/repositories/{repo['id']}/analysis")
    assert response.status_code == 201
    created = response.json()["run"]
    assert created["status"] == "queued"
    assert created["repository_full_name"] == "octocat/Hello-World"
    assert created["analysis_version"] == "0.1.0"  # the fake provider's version

    done = _wait_for_status(client, created["id"], "completed")
    assert done["started_at"] is not None
    assert done["completed_at"] is not None
    assert done["duration_ms"] is not None

    detail = client.get(f"/api/v1/repositories/{repo['id']}").json()
    assert detail["analysis_status"] == "analyzed"
    assert detail["last_analysis_job_id"] == created["id"]
    assert detail["last_analysis_at"] is not None


def test_duplicate_active_run_returns_409(client: TestClient) -> None:
    _register(client)
    _active_github.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World")
    _cfg["hold"] = 60.0  # keep the first run QUEUED so the second conflicts

    first = client.post(f"/api/v1/repositories/{repo['id']}/analysis")
    assert first.status_code == 201
    second = client.post(f"/api/v1/repositories/{repo['id']}/analysis")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "analysis_already_active"

    # Clean up the sleeping run so no task leaks into the next test.
    run_id = first.json()["run"]["id"]
    assert client.post(f"/api/v1/analysis/{run_id}/cancel").status_code == 200


# ── Cancellation ────────────────────────────────────────────────────────
def test_cancel_queued_run(client: TestClient) -> None:
    _register(client)
    _active_github.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World")
    _cfg["hold"] = 60.0

    created = client.post(f"/api/v1/repositories/{repo['id']}/analysis").json()["run"]
    response = client.post(f"/api/v1/analysis/{created['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["run"]["status"] == "cancelled"

    # The repository lifecycle is reset; a second cancel is a conflict.
    assert (
        client.get(f"/api/v1/repositories/{repo['id']}").json()["analysis_status"] == "not_analyzed"
    )
    again = client.post(f"/api/v1/analysis/{created['id']}/cancel")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "analysis_not_cancellable"


def test_cancel_running_run(client: TestClient) -> None:
    _register(client)
    _active_github.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World")
    _cfg["delay"] = 30.0

    created = client.post(f"/api/v1/repositories/{repo['id']}/analysis").json()["run"]
    _wait_for_status(client, created["id"], "running")
    response = client.post(f"/api/v1/analysis/{created['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["run"]["status"] == "cancelled"
    # The provider aborts on the cancel event — the run must stay cancelled.
    _wait_for_status(client, created["id"], "cancelled")


# ── Failure modes ───────────────────────────────────────────────────────
def test_provider_failure_marks_run_failed(client: TestClient) -> None:
    _register(client)
    _active_github.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World")
    _cfg["fail"] = True

    created = client.post(f"/api/v1/repositories/{repo['id']}/analysis").json()["run"]
    done = _wait_for_status(client, created["id"], "failed")
    assert done["failure_reason"] is not None
    assert client.get(f"/api/v1/repositories/{repo['id']}").json()["analysis_status"] == "failed"


def test_provider_timeout_marks_run_failed(client: TestClient) -> None:
    _register(client)
    _active_github.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World")
    _cfg["delay"] = 60.0
    _cfg["timeout"] = 0.2

    created = client.post(f"/api/v1/repositories/{repo['id']}/analysis").json()["run"]
    done = _wait_for_status(client, created["id"], "failed")
    assert "timed out" in (done["failure_reason"] or "")


# ── Ownership scoping ───────────────────────────────────────────────────
def test_runs_are_scoped_to_their_owner(client: TestClient) -> None:
    _register(client, email="alice@example.com")
    _active_github.repos["alice/repo"] = _repo_data("alice/repo")
    repo = _import(client, "alice/repo")
    created = client.post(f"/api/v1/repositories/{repo['id']}/analysis").json()["run"]
    _wait_for_status(client, created["id"], "completed")

    _register(client, email="bob@example.com")
    assert client.get(f"/api/v1/analysis/{created['id']}").status_code == 404
    assert client.post(f"/api/v1/analysis/{created['id']}/cancel").status_code == 404
    assert client.delete(f"/api/v1/analysis/{created['id']}").status_code == 404
    assert client.get("/api/v1/analysis").json()["total"] == 0


# ── Listing + delete ────────────────────────────────────────────────────
def test_list_and_per_repository_endpoints(client: TestClient) -> None:
    _register(client)
    _active_github.repos["octocat/alpha"] = _repo_data("octocat/alpha")
    _active_github.repos["octocat/beta"] = _repo_data("octocat/beta")
    repo_a = _import(client, "octocat/alpha")
    repo_b = _import(client, "octocat/beta")
    run_a = client.post(f"/api/v1/repositories/{repo_a['id']}/analysis").json()["run"]
    run_b = client.post(f"/api/v1/repositories/{repo_b['id']}/analysis").json()["run"]
    _wait_for_status(client, run_a["id"], "completed")
    _wait_for_status(client, run_b["id"], "completed")

    all_runs = client.get("/api/v1/analysis").json()
    assert all_runs["total"] == 2
    assert {item["repository_full_name"] for item in all_runs["items"]} == {
        "octocat/alpha",
        "octocat/beta",
    }

    filtered = client.get("/api/v1/analysis", params={"status": "completed"}).json()
    assert filtered["total"] == 2

    per_repo = client.get(f"/api/v1/repositories/{repo_a['id']}/analysis").json()
    assert per_repo["total"] == 1
    assert per_repo["items"][0]["id"] == run_a["id"]

    paged = client.get("/api/v1/analysis", params={"page": 1, "page_size": 1}).json()
    assert paged["total_pages"] == 2
    assert len(paged["items"]) == 1


def test_delete_terminal_run_and_reject_active(client: TestClient) -> None:
    _register(client)
    _active_github.repos["octocat/Hello-World"] = _repo_data("octocat/Hello-World")
    repo = _import(client, "octocat/Hello-World")
    _cfg["hold"] = 60.0

    active = client.post(f"/api/v1/repositories/{repo['id']}/analysis").json()["run"]
    blocked = client.delete(f"/api/v1/analysis/{active['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "analysis_active"
    assert client.post(f"/api/v1/analysis/{active['id']}/cancel").status_code == 200

    _cfg["hold"] = 0.0  # the next run must actually dispatch and complete
    terminal = client.post(f"/api/v1/repositories/{repo['id']}/analysis").json()["run"]
    _wait_for_status(client, terminal["id"], "completed")
    assert client.delete(f"/api/v1/analysis/{terminal['id']}").status_code == 204
    assert client.get(f"/api/v1/analysis/{terminal['id']}").status_code == 404
