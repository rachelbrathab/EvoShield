"""Local-provider JWT encoding/decoding (HS256).

Tokens are self-contained and carry the same claim shape as Supabase tokens
(`sub`, `email`, `exp`), so downstream code treats them identically. The
Supabase provider verifies tokens signed by Supabase instead.
"""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.domains.identity.ports import TokenClaims


def create_access_token(
    *,
    sub: str,
    email: str,
    provider: str,
    expires_in_seconds: int | None = None,
) -> str:
    """Issue a signed HS256 access token for the given subject."""
    settings = get_settings()
    expires = expires_in_seconds or settings.session_max_age_seconds
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "email": email,
        "provider": provider,
        "iat": now,
        "exp": now + timedelta(seconds=expires),
    }
    return jwt.encode(payload, settings.session_jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> TokenClaims:
    """Decode and verify an access token; raises on invalid/expired tokens."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.session_jwt_secret,
        algorithms=["HS256"],
        options={"require": ["sub", "exp"]},
    )
    return TokenClaims(
        sub=str(payload["sub"]),
        email=str(payload.get("email", "")),
        provider=str(payload.get("provider", "local")),
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )
