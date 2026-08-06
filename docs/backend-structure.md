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
│   │   ├── github/           GitHub integration (Sprint 3) — repository contract (RepositoryRead)
│   │   ├── analysis/         Repository analysis (Sprint 4)
│   │   ├── scanners/         Scanner engine: Trivy/Syft/Grype/Semgrep/Gitleaks (Sprint 5)
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
| `models/` | ORM entities — `User`, `AuthCredential`, and `Repository` with its `AnalysisStatus` lifecycle enum. | Single source of truth for schema (Alembic autogenerate). The Repository aggregate carries the analysis-status trio (`analysis_status`, `last_analysis_at`, `last_analysis_job_id`) so Sprint 4/5 pipelines have a stable, already-migrated status mechanism (Sprint 3 preparation). |
| `repositories/` | Query surface. | Repos isolate SQL from business logic; domain-owned when a domain has private aggregates. |
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

See `docs/module-dependency.md` for the diagram.
