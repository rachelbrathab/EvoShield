"""Tests for the security middleware (host validation + response headers)."""

from fastapi.testclient import TestClient


def test_security_headers_present_on_response(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_unknown_host_rejected(client: TestClient) -> None:
    """TrustedHostMiddleware must reject Host headers outside the allowlist."""
    response = client.get("/api/v1/health", headers={"Host": "evil.example.com"})
    assert response.status_code == 400


def test_allowed_host_accepted(client: TestClient) -> None:
    # TestClient sends "testserver", which is in ALLOWED_HOSTS.
    response = client.get("/api/v1/health")
    assert response.status_code == 200
