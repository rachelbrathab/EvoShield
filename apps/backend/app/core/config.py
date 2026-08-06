"""Application settings — the single source of truth for configuration.

Values are resolved from (in order of precedence):
1. Real environment variables
2. A `.env` file in the working directory (see `.env.example`)
3. The defaults below

`get_settings()` is cached so the whole process shares one immutable
settings object.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── App ────────────────────────────────────────────────────────────
    app_name: str = "EvoShield API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # ── HTTP ───────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000"]
    # Host-header allowlist for TrustedHostMiddleware. "testserver" keeps
    # Starlette's TestClient working; production overrides with the public
    # app domain(s).
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]

    # ── Database ───────────────────────────────────────────────────────
    # Postgres (asyncpg) is the production target — Supabase-managed.
    # SQLite (aiosqlite) is the zero-dependency local dev fallback.
    database_url: str = "sqlite+aiosqlite:///./evoshield-dev.db"

    # ── Auth (Sprint 2) ────────────────────────────────────────────────
    # Provider selection: "auto" → Supabase when credentials are configured,
    # otherwise the local provider (zero-dependency dev fallback, mirroring
    # the SQLite database fallback).
    auth_provider: str = "auto"
    # httpOnly session cookie holding the access token.
    session_cookie_name: str = "evoshield_session"
    session_cookie_secure: bool = False  # True behind TLS in production
    # Local-provider token lifetime (Supabase tokens carry their own exp).
    session_max_age_seconds: int = 12 * 60 * 60
    # Shared secret for local-provider HS256 tokens (dev default; override
    # in real environments). Supabase verification uses SUPABASE_JWT_SECRET.
    # >= 32 bytes (256 bits) per RFC 7518 §3.2 for HS256.
    session_jwt_secret: str = "dev-only-session-secret-change-me-0123456789"
    # Frontend origin for OAuth post-login redirects.
    frontend_url: str = "http://localhost:3000"

    # ── Supabase ───────────────────────────────────────────────────────
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None

    # ── GitHub OAuth ───────────────────────────────────────────────────
    github_client_id: str | None = None
    github_client_secret: str | None = None
    # Absolute URL GitHub redirects back to after authorization, e.g.
    #   http://localhost:8000/api/v1/auth/oauth/github/callback
    github_redirect_uri: str | None = None
    # REST API base (override for GitHub Enterprise). The repository
    # integration client (Sprint 3A) targets this.
    github_api_url: str = "https://api.github.com"

    # ── Analysis (Sprint 4A) ───────────────────────────────────────────
    # Provider selection: "fake" simulates runs until real scanners land in
    # Sprint 5 ("trivy", "syft", … become valid values then).
    analysis_provider: str = "fake"
    # How long the fake provider "scans" (seconds).
    analysis_fake_delay_seconds: float = 4.0
    # Dev knob: make the fake provider fail so the FAILED path can be seen.
    analysis_fake_fail: bool = False
    # How long a run sits in QUEUED before the orchestrator dispatches it.
    analysis_queued_hold_seconds: float = 2.0
    # Hard cap on one provider execution; on expiry the run is marked FAILED.
    analysis_run_timeout_seconds: float = 120.0

    # ── Observability ──────────────────────────────────────────────────
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
