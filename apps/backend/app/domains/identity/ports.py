"""Identity domain ports — the interfaces this domain depends on.

The domain depends on an `AuthProvider` port, never on a concrete provider.
Two implementations exist: `SupabaseAuthProvider` (production) and
`LocalAuthProvider` (zero-dependency dev fallback). See `factory.py`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AuthUser:
    """Normalized identity returned by a provider."""

    id: str
    email: str
    full_name: str | None
    avatar_url: str | None
    provider: str
    provider_sub: str


@dataclass(frozen=True)
class AuthResult:
    """Successful authentication: access token + normalized identity."""

    access_token: str
    token_type: str
    expires_in: int
    user: AuthUser


@dataclass(frozen=True)
class TokenClaims:
    """Claims decoded from an access token."""

    sub: str
    email: str
    provider: str
    exp: datetime


class AuthProvider(Protocol):
    """Port every auth provider implements."""

    async def register(self, email: str, password: str, full_name: str | None) -> AuthResult: ...

    async def login(self, email: str, password: str) -> AuthResult: ...

    async def verify_token(self, token: str) -> TokenClaims: ...

    async def logout(self, token: str) -> None: ...
