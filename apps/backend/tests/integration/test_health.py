"""Tests for the system health endpoint."""

from fastapi.testclient import TestClient


def test_health_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "test"
    assert payload["database"] in {"ok", "unavailable"}
    assert "timestamp" in payload


def test_health_database_probe_reports_ok_on_sqlite(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_root_returns_service_name(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "EvoShield API"
