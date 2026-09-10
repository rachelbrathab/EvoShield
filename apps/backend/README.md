# EvoShield Backend

FastAPI service — the API layer of the EvoShield platform.

## Layout (clean architecture, domain-oriented)

```
app/
├── api/          HTTP layer: routers, dependencies, request/response wiring
│   └── routers/  One module per resource (health, auth, repositories, …)
├── core/         Cross-cutting: config, logging, exceptions, security
├── db/           Engine + session factory (SQLAlchemy async)
├── domains/      Business logic per domain (identity, health, github,
│                 analysis, scanners, intelligence, remediation) — each
│                 owns service.py + schemas.py (+ ports.py where external)
├── models/       ORM models (SQLAlchemy 2.0)
├── repositories/ Data access per aggregate
├── schemas/      Shared Pydantic contracts (cross-domain DTOs)
├── workers/      Long-running cross-domain pipelines (Sprint 5+)
└── utils/        Pure helpers
```

See `docs/backend-structure.md`, `docs/domain-overview.md` and
`docs/module-dependency.md` for the full architecture.

## Tests

```
tests/
├── unit/         Pure logic with injected dependencies (per domain)
├── integration/  Full FastAPI stack + live test database
└── e2e/          Full-stack scenarios (Sprint 13)
```

## Run locally

```bash
uv sync                  # creates .venv with Python 3.12 (uv-managed)
uv run uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health:    http://localhost:8000/api/v1/health
- Auth:      http://localhost:8000/api/v1/auth/register|login|logout|me

## Docker & operations (Sprint 8)

The image ships the pinned scanner toolchain (Trivy 0.74.0, Gitleaks 8.30.1,
Semgrep 1.176.1, Syft 1.51.1, Grype 0.118.0) and git — see the Dockerfile
for how to bump a version safely.

Restart recovery: runs interrupted by a server restart are marked failed at
startup (lifespan hook, disable with `REAPER_ENABLED=false`). For
multi-worker deployments run recovery once instead:

```bash
python -m app.cli recover-runs
```

## Authentication (Sprint 2)

The `identity` domain ships with a provider port and two adapters:

- **local** — argon2 password hashing + HS256 JWT (zero dependencies; the
  default for dev and tests).
- **supabase** — server-side Supabase Auth + JWT verification with
  `SUPABASE_JWT_SECRET`.

`AUTH_PROVIDER=auto` picks Supabase when its credentials are set, otherwise
falls back to local. Sessions use an httpOnly cookie (`evoshield_session`);
the bearer header is also accepted. GitHub OAuth needs `GITHUB_CLIENT_ID`,
`GITHUB_CLIENT_SECRET` and `GITHUB_REDIRECT_URI` configured.

See `docs/adr/0005-identity-auth.md` and `docs/api.md`.

## Configuration

Copy `.env.example` → `.env`. Defaults target a zero-setup SQLite dev database;
production uses Supabase Postgres (see `docs/adr/0001-database-layer.md`).
