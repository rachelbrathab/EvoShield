# EvoShield Architecture

This document is the living architecture reference for EvoShield. It is updated
as sprints land. Sprint 1 establishes the skeleton; deeper detail is added per
sprint in the sprint-plan documents.

## 1. Goals & non-goals

**Goals**

- A production-grade, modular SaaS monorepo that scales from college project to
  real deployment.
- Clean separation of concerns so each layer is testable in isolation.
- Security-first by construction: secrets never hardcoded, scanners pinned,
  least-privilege auth.

**Non-goals (right now)**

- Premature distribution, multi-tenant billing, or a public plugin SDK.
- Replacing the industry scanners — we orchestrate them.

## 2. Monorepo topology

```
apps/frontend   Next.js App Router SPA+SSR. Server components by default;
                "use client" only where interactivity requires it.
apps/backend    FastAPI service. Owns all business logic and data.
packages/       Shared code (typed API contracts, future SDKs).
docs/           Architecture, sprint plans, ADRs (decision records).
scripts/        Root-level developer tooling.
.github/        CI (lint, typecheck, tests, build) on push + PR.
```

**Why a monorepo?** One review surface, atomic cross-cutting changes, a single
source of truth for CI — while keeping `apps/*` independently deployable on
Render later.

## 3. Backend clean architecture

Layered, dependency-inverted. HTTP knows nothing about storage.

```
HTTP layer      app/api/            routers + deps (FastAPI)
    ↓
Orchestration   app/workers/        cross-domain pipelines (off request path)
    ↓
Domains         app/domains/*/      one package per business domain
                                    (service.py + schemas.py + ports.py)
    ↓
Repository      app/repositories/   data access per aggregate
    ↓
Models          app/models/         SQLAlchemy 2.0 ORM entities
```

Cross-cutting:

- `app/core/` — config (pydantic-settings), logging, exception taxonomy, security.
- `app/domains/` — **business logic per domain** (identity, health, github,
  analysis, scanners, intelligence, prediction, recommendation, reports,
  chat). Domains never import each other; orchestration lives in `workers/`.
- `app/schemas/` — shared Pydantic contracts; domain-specific schemas live in
  their domain.
- `app/db/` — async engine + session factory.
- `app/utils/` — pure helpers (no I/O).

See `docs/backend-structure.md` for the folder map, `docs/domain-overview.md`
for per-domain ownership, and `docs/module-dependency.md` for the dependency
diagram.

**Rules**

- Routers only parse/validate and call one domain (or the orchestration layer);
  no business logic.
- Domains never import sibling domains — composition happens in `workers/`.
- Domains depend on ports, not tools: scanner binaries, GitHub API, LLM vendors
  are adapters injected behind domain interfaces.
- Models never leak into schemas; explicit mappers live in repositories.
- Domains are the unit of business testing (unit + integration); repos are
  tested against the DB.

## 4. Frontend architecture

- **App Router** with React Server Components for pages (fast, secure, no
  client bundle for static content).
- **Server → client boundary**: interactive islands (`"use client"`) for forms,
  charts, and live components (e.g. `HealthBadge`).
- **Styling**: Tailwind v4 + shadcn/ui (Base UI). Dark-first design tokens in
  `globals.css` — GitHub/Vercel/Linear-inspired.
- **Data flow**: `lib/api.ts` is the single hand-written API client today; a
  typed client is generated from the backend OpenAPI spec in a later sprint.
- **State**: React state + server data first. TanStack Query is considered in
  Sprint 4+ once data-heavy views land.

## 5. Data layer

- **SQLAlchemy 2.0 async** (`asyncpg` for Postgres, `aiosqlite` for local dev).
- **Alembic** for migrations — schema evolves only via migrations, never by hand.
- **Postgres-first, SQLite-tolerant**: all models and queries are dialect-safe
  (UUIDs via `uuid` with SQLite text storage).
- The Postgres path is exercised in CI with a live Postgres 16 service
  container; SQLite is the local default.
- **Analysis status is first-class.** The `repositories` table (Sprint 3
  preparation) carries a per-repository analysis lifecycle
  (`not_analyzed · queued · analyzing · analyzed · failed · cancelled`) as
  an enum-backed VARCHAR — validated in Python, no DB CHECK constraint, so
  new states are code-only additions. Scan-specific data never lands on this
  table: scanners get their own tables (Sprint 5) and only flip
  `analysis_status` on the repository row. See `docs/database.md` and
  `docs/adr/0006-analysis-status.md`.
- See `docs/adr/0001-database-layer.md` for the full decision.

## 6. Security posture

- Secrets via environment variables only (`pydantic-settings` + `.env`, gitignored).
- CORS allowlist driven by config, disabled in prod as appropriate.
- Host-header validation (`TrustedHostMiddleware`) + security response headers
  (nosniff, X-Frame-Options, Referrer-Policy, HSTS in prod) — see
  `app/core/security.py`.
- Docs (`/docs`) disabled in production.
- Dependency scanner pinning: semver ranges in `pyproject.toml` + lockfiles.
- Supply chain scan findings never contain raw source code.
- **Authentication (Sprint 2)** — the `identity` domain owns all auth logic:
  an `AuthProvider` port with a local adapter (argon2 + HS256 JWT, the
  zero-dependency dev/test default) and a Supabase adapter (server-side auth
  + JWT verification). Sessions travel in an **httpOnly, SameSite=Lax cookie**
  so browser JS never touches the raw token; the bearer header is accepted
  for API clients. GitHub OAuth uses a state cookie to prevent login CSRF.
  See `docs/adr/0005-identity-auth.md`.

## 7. Observability

- Structured logging via `app/core/logging.py` (JSON-ready formatter, request
  context).
- `/api/v1/health` exposes app version, environment and DB connectivity —
  consumed by the frontend `HealthBadge`.

## 8. Roadmap hooks

- Sprint 2 ✅: authentication in `domains/identity/` (provider port + JWT
  sessions + GitHub OAuth). Sprint 3's GitHub repository integration reuses
  the authenticated user/session established here.
- Sprint 3: GitHub API client + repository ingestion in `domains/github/`
  (defines the source-provider port; GitLab/Bitbucket/Azure DevOps implement
  it later). The `repositories` table and the `RepositoryRead` contract
  already exist (Sprint 3 preparation), so ingestion writes against a stable
  schema that carries the analysis-status lifecycle.
- Sprint 5: scanner orchestration in `domains/scanners/`, run as background
  jobs from `app/workers/`. Pipelines report progress by transitioning
  `Repository.analysis_status` (already migrated) and write findings to their
  own tables.
- Sprint 7: `domains/prediction/` with pandas/NumPy/scikit-learn, feature store
  fed from repository intelligence tables.
