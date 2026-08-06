"""HTTP security hardening: host-header validation and security headers.

A DevSecOps platform should practice what it preaches. These two layers are
cheap, framework-standard, and close the most common HTTP attack surfaces:

- `TrustedHostMiddleware` rejects requests whose `Host` header is not in the
  allowlist (Host-header poisoning, cache poisoning, some SSRF variants).
- A small response-header middleware pins security headers so browsers treat
  responses defensively.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import get_settings


def apply_security_middleware(app: FastAPI) -> None:
    """Attach host validation and security response headers to the app."""
    settings = get_settings()

    # IMPORTANT — ordering: Starlette wraps the EARLIEST-added middleware
    # OUTERMOST. TrustedHostMiddleware must therefore be added first so host
    # validation runs before every other layer (including CORS). Call this
    # function before registering CORS in the app factory.
    if settings.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts,
            www_redirect=False,
        )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Mitigate MIME sniffing on proxied assets; modern XSS is handled by CSP,
        # which is added once the app shell exists (Sprint 2).
        response.headers.setdefault("X-XSS-Protection", "0")
        if settings.environment == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response
