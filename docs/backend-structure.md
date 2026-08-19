# Backend Structure

> Companion to `docs/architecture.md`. Documents the FastAPI backend layout
> and the reasoning behind every folder.

## Directory tree

```
apps/backend/
├── app/
│   ├── api/                  HTTP layer (routers + FastAPI dependencies)
│   │   └── routers/          One module per resource (health, auth, …)
│   ├── core/                 Cross-cutting: config, logging, exceptions, security
│   ├── db/                   Engine + session factory (SQLAlchemy async)
│   ├── domains/              Business domains — the heart of the system
│   │   ├── identity/         Authentication + user profiles (Sprint 2 ✅)
│   │   ├── health/           Liveness + dependency probes (reference impl.)
│   │   ├── github/           GitHub integration (Sprint 3A ✅) — client, service, repository, contracts
│   │   ├── analysis/         Analysis infrastructure (Sprint 4A ✅) — orchestrator, provider port, fake provider
│   │   ├── scanners/         Scanner engine: Trivy/Syft/Grype/Semgrep/Gitleaks (Sprint 5A/5B) — including GitHubRepositorySource for repo acquisition
│   │   ├── intelligence/     Temporal repository intelligence (Sprint 6)
│   │   ├── prediction/       Future-risk engine (Sprint 7)
│   │   ├── recommendation/   Remediation guidance (Sprint 8)
│   │   ├── reports/          Report generation (Sprint 9)
│   │   └── chat/             AI security assistant (Sprint 10)
│   ├── models/               SQLAlchemy ORM models (single schema source); Repository + AnalysisStatus (Sprint 3 prep)
│   ├── repositories/         Shared data-access surface (per-domain when needed)
│   ├── schemas/              Shared Pydantic contracts across domains
│   ├── workers/              Long-running cross-domain pipelines (Sprint 5)
│   └── utils/                Pure helpers (no application imports)
├── alembic/                  Migrations
├── tests/
│   ├── unit/                 Pure logic, injected dependencies
│   │   └── domains/          Per-domain unit tests (mirrors app/domains/)
│   ├── integration/          Real FastAPI stack + live test database
│   └── e2e/                  Full-stack scenarios (Sprint 13)
├── Dockerfile                uv multi-stage, non-root, healthcheck
├── pyproject.toml            Dependencies + ruff/pyright/pytest config
└── uv.lock                   Locked dependency graph
```

## Why each folder exists

| Folder | Purpose | Decision rationale |
| --- | --- | --- |
| `api/` | Parsing/validation/wiring only. No business logic. | Keeps the HTTP surface thin and replaceable. |
| `core/` | Config, logging, exception taxonomy, security middleware. | Infrastructure every layer needs — kept central, not per-domain. |
| `db/` | Async engine + session factory. | One engine per process; sessions request-scoped via DI. |
| `domains/` | Business logic per domain. | **The key change**: replaces the generic `services/` bucket. Each domain owns its logic + schemas, so unrelated code never mixes. |
| `domains/identity/` | Register/login/logout, JWT sessions, GitHub OAuth, user profiles. | Auth is its own bounded context: providers (local + Supabase) sit behind a port, so swapping identity backends never touches other domains (ADR 0005). |
| `domains/analysis/` | Run lifecycle orchestration — `AnalysisRun` state machine, `AnalysisProvider` port, fake provider, factory, owner-scoped data access, API contracts. | The "operating system" for the analysis engine: scanners plug in as provider adapters, so adding Trivy/Syft/etc. never touches the API, DB or UI (ADR 0008). |
| `models/` | ORM entities — `User`, `AuthCredential`, `ProviderToken`, `Repository` (with its `AnalysisStatus` lifecycle enum + GitHub metadata), and `AnalysisRun` (run history, Sprint 4A). | Single source of truth for schema (Alembic autogenerate). `Repository` carries the analysis-status trio plus provider metadata (Sprint 3A); `ProviderToken` stores per-user upstream access tokens; `AnalysisRun` records per-run history. |
| `repositories/` | Query surface. | Repos isolate SQL from business logic; domain-owned when a domain has private aggregates. `provider_token.py` is shared because both `identity` (write) and `github` (read) touch the table. |
| `schemas/` | Shared contracts only. | Domain-specific schemas live in the domain; this folder holds cross-domain DTOs. |
| `workers/` | Background pipelines. | Scan orchestration etc. must not block the request path. |
| `utils/` | Pure helpers. | No imports from `app.*` — guaranteed side-effect-free. |

## Dependency rules (enforced by convention + review)

1. `api → domains` (and `api → core/db/utils`). Routers never call models or
   repositories directly.
2. `domains → core/db/models/utils`. Domains **never import each other**.
3. `workers → domains` (composition) — the only place allowed to orchestrate
   multiple domains.
4. `repositories → models`. Nothing outside repositories queries the ORM.
5. Schemas: domain-owned by default; `schemas/` only for cross-domain DTOs.

## Github domain layout (Sprint 3A)

```
app/domains/github/
├── ports.py           GitHubRepoProvider port, GitHubRepoData, client factory, token provider
├── github_client.py   GitHub REST adapter — every GitHub-specific detail (URLs, headers,
│                      payload mapping, rate-limit/error translation) is isolated here
├── service.py         RepositoryService — import (idempotent upsert), sync, list/get/delete,
│                      GitHub browse; depends on ports, never on the concrete client
├── repository.py      RepositoryRepository — owner-scoped data access with search/filter/sort
└── schemas.py         RepositoryRead (extended), list/import/sync/search contracts
```

## Analysis domain layout (Sprint 4A)

```
app/domains/analysis/
├── ports.py            AnalysisProvider port + AnalysisExecutionContext; the seam scanners implement
├── orchestrator.py     AnalysisOrchestrator — run state machine (queue/dispatch/complete/fail/cancel),
│                       repo lifecycle mirror, timeout + cancellation, background simulation task
├── repository.py       AnalysisRunRepository — owner-scoped run queries (run → repository → owner)
├── schemas.py          AnalysisRunRead, list/create/cancel contracts
├── factory.py          build_analysis_provider() — selects the provider from settings
└── providers/
    └── fake.py         FakeAnalysisProvider — simulated run (delay/fail/cancel), the Sprint 4A default
```

Scanners (Sprint 5) land as sibling adapters under `providers/` — the
orchestrator, repository and API stay untouched (see `docs/adr/0008-analysis-domain.md`).

See `docs/module-dependency.md` for the diagram.
