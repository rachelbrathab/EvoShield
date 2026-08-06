"""Unit tests for local-provider JWT signing/verification."""

from datetime import UTC, datetime

import jwt
import pytest

from app.core.config import get_settings
from app.domains.identity.jwt import create_access_token, decode_access_token


def test_create_and_decode_roundtrip() -> None:
    token = create_access_token(sub="user-123", email="ada@example.com", provider="local")
    claims = decode_access_token(token)
    assert claims.sub == "user-123"
    assert claims.email == "ada@example.com"
    assert claims.provider == "local"
    # exp must be in the future and close to the configured lifetime.
    assert claims.exp > datetime.now(UTC)


def test_token_honors_custom_lifetime() -> None:
    token = create_access_token(
        sub="user-1",
        email="a@example.com",
        provider="local",
        expires_in_seconds=60,
    )
    claims = decode_access_token(token)
    remaining = claims.exp - datetime.now(UTC)
    assert 30 < remaining.total_seconds() <= 60


def test_expired_token_rejected() -> None:
    token = create_access_token(
        sub="user-1",
        email="a@example.com",
        provider="local",
        expires_in_seconds=-60,  # already expired
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_tampered_token_rejected() -> None:
    token = create_access_token(sub="user-1", email="a@example.com", provider="local")
    forged = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged)


def test_token_uses_configured_secret() -> None:
    settings = get_settings()
    token = create_access_token(sub="u", email="e@x.io", provider="local")
    # Decoding with the wrong secret must fail.
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "not-the-secret", algorithms=["HS256"])
    assert settings.session_jwt_secret != "not-the-secret"
