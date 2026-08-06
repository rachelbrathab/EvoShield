"""Integration tests for the authentication API (local provider).

These run against the real FastAPI app + SQLite test database. The local
provider is active because no Supabase credentials are configured in the
test environment (see `app/domains/identity/factory.py`).
"""

import re

from fastapi.testclient import TestClient

SESSION_COOKIE = "evoshield_session"

REGISTER_PAYLOAD = {
    "email": "ada@example.com",
    "password": "correct-horse-battery",
    "full_name": "Ada Lovelace",
}


def _register(client: TestClient, **overrides: str):
    """Register the shared test user; returns the TestClient response."""
    payload = {**REGISTER_PAYLOAD, **overrides}
    return client.post("/api/v1/auth/register", json=payload)


def test_register_creates_profile_and_session_cookie(client: TestClient) -> None:
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["full_name"] == "Ada Lovelace"
    assert body["user"]["auth_provider"] == "local"
    # Session cookie is set (httpOnly) and carries the access token.
    cookie = response.cookies.get(SESSION_COOKIE)
    assert cookie == body["access_token"]


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    assert _register(client).status_code == 201
    response = _register(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_register_validates_email_and_password(client: TestClient) -> None:
    bad_email = _register(client, email="not-an-email")
    assert bad_email.status_code == 422
    short_password = _register(client, email="bob@example.com", password="short")
    assert short_password.status_code == 422


def test_login_returns_token_and_sets_cookie(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "correct-horse-battery"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "ada@example.com"
    assert response.cookies.get(SESSION_COOKIE) == body["access_token"]


def test_login_rejects_wrong_password(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_login_rejects_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever-pass"},
    )
    assert response.status_code == 401


def test_me_returns_profile_with_session_cookie(client: TestClient) -> None:
    _register(client)
    # TestClient persists the Set-Cookie from register in its cookie jar.
    assert client.cookies.get(SESSION_COOKIE)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    profile = response.json()
    assert profile["email"] == "ada@example.com"
    assert profile["auth_provider"] == "local"
    assert profile["created_at"] is not None


def test_me_accepts_bearer_token(client: TestClient) -> None:
    body = _register(client).json()
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_session_check_validates_cookie(client: TestClient) -> None:
    _register(client)
    assert client.cookies.get(SESSION_COOKIE)
    response = client.get("/api/v1/auth/session/check")
    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


def test_logout_clears_session(client: TestClient) -> None:
    _register(client)
    assert client.cookies.get(SESSION_COOKIE)
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert not client.cookies.get(SESSION_COOKIE)
    # After logout the cookie is cleared, so the session is no longer valid.
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401


def test_oauth_unconfigured_returns_provider_error(client: TestClient) -> None:
    """Without GitHub credentials the OAuth start endpoint fails cleanly."""
    response = client.get("/api/v1/auth/oauth/github")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"


def test_register_creates_row_in_users_table(client: TestClient) -> None:
    _register(client)
    # The app-side profile is persisted — re-login succeeds and the same
    # user id is returned (no duplicate rows).
    first = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "correct-horse-battery"},
    ).json()
    second = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "correct-horse-battery"},
    ).json()
    assert first["user"]["id"] == second["user"]["id"]
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        first["user"]["id"],
    )
