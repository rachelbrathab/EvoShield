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
- **List-view state is URL-persisted (Sprint 3B)**: the repository list
  serializes its whole toolbar (search, filters, sort + direction, page,
  page-size) into the query string via the pure `lib/repository-view.ts`
  module — refresh, share and back/forward restore the exact view. Heavier
  interactive surfaces (the import dialog's GitHub browser) are lazy-loaded
  with `next/dynamic`.
- **Error UX is code-aware (Sprint 3B)**: `lib/repository-errors.ts` maps
  backend error codes (`github_rate_limited`, `github_token_invalid`,
  `github_not_connected`, `github_forbidden`, `not_found`, network failures)
  to friendly copy and the right action (retry vs. reconnect).
- **Frontend tests (Sprint 3B)**: Vitest + React Testing Library cover the
  pure view-state/search/format/error modules and key presentational
  components (pagination, card, empty/error states, search highlight).

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
- **Analysis runs are a first-class aggregate (Sprint 4A).** The `analysis`
  domain owns the *lifecycle of a run* — `analysis_runs` records one
  execution per repository (status, timing, version, failure reason); the
  orchestrator mirrors run state onto `repositories.analysis_status` so
  cards/details update without redesign. Scanners plug in behind an
  `AnalysisProvider` port and are selected by settings — adding Trivy later
  is one adapter + one config value (see `docs/adr/0008-analysis-domain.md`).
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
- **GitHub integration (Sprint 3A)** — the OAuth callback persists the GitHub
  access token in `provider_tokens`; the `github` domain calls the GitHub
  REST API through a provider port (`GitHubRepoProvider`). See
  `docs/adr/0007-github-integration.md`.

## 7. Observability

- Structured logging via `app/core/logging.py` (JSON-ready formatter, request
  context).
- `/api/v1/health` exposes app version, environment and DB connectivity —
  consumed by the frontend `HealthBadge`.

## 8. Roadmap hooks

- Sprint 2 ✅: authentication in `domains/identity/` (provider port + JWT
  sessions + GitHub OAuth). Sprint 3's GitHub repository integration reuses
  the authenticated user/session established here.
- Sprint 3A ✅: repository integration in `domains/github/` — a source-provider
  port (`GitHubRepoProvider`) with a GitHub REST adapter, idempotent import,
  in-place sync, owner-scoped queries, and a GitHub repo browser for the
  import dialog. The identity service persists the GitHub OAuth access token
  in `provider_tokens` (Sprint 3A), so the API can act as the user. The
  `repositories` table and the `RepositoryRead` contract (Sprint 3
  preparation) carry the GitHub metadata; GitLab/Bitbucket/Azure DevOps later
  ship as new adapters implementing the same port.
- Sprint 3B ✅: repository UX polish — URL-persisted list view state
  (search/filter/sort/pagination), search highlighting, topic chips,
  copy-URL/clone actions, code-aware empty/error states, lazy-loaded
  dialogs, and the first frontend test suite (Vitest + RTL).
- Sprint 4A ✅: analysis infrastructure in `domains/analysis/` — the
  `AnalysisRun` aggregate + orchestrator state machine, an
  `AnalysisProvider` port with a fake simulation adapter (configurable
  delay/failure/cancel), timeout + cancellation, owner-scoped run API
  (start/list/detail/cancel/delete), and a run history UI with live polling
  and a timeline. No scanner runs yet; the orchestration layer is the
  "operating system" Sprint 5 scanners plug into (see
  `docs/adr/0008-analysis-domain.md`).
- Sprint 4B: real analysis capabilities on top of the orchestration layer.
- Sprint 5: scanner orchestration in `domains/scanners/`, run as background
  jobs from `app/workers/`. Pipelines report progress by transitioning
  `Repository.analysis_status` (already migrated) and write findings to their
  own tables.
- Sprint 7: `domains/prediction/` with pandas/NumPy/scikit-learn, feature store
  fed from repository intelligence tables.
