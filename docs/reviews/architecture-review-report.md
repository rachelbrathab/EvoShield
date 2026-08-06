# Architecture Review Report — Backend Domain Restructure

> **Date:** 2026-08-03
> **Reviewer:** Lead Software Architect
> **Scope:** backend architecture ahead of Sprint 2 (authentication)
> **Status:** ✅ Implemented and validated

---

## Executive summary

Sprint 1's backend was architecturally sound but **not yet ready for the
DevSecOps pipeline**. It had a generic `services/` folder, flat schema
ownership, no domain boundaries, no orchestration home, and a flat test
layout. This review reorganized the backend into a **domain-oriented
architecture** without adding features and without breaking existing
behavior. No authentication was implemented (as instructed).

## What changed

| Area | Before | After |
| --- | --- | --- |
| Business logic | `app/services/` (flat bucket) | `app/domains/<domain>/` (one package per domain) |
| Health logic | `services/health_service.py` + `schemas/health.py` | `domains/health/service.py` + `domains/health/schemas.py` |
| Domain boundaries | None (only comments in router) | 9 domains: health, github, analysis, scanners, intelligence, prediction, recommendation, reports, chat |
| Orchestration | Nowhere | `app/workers/` (cross-domain pipelines) |
| Schemas | Global pile | Domain-owned by default; `schemas/` reserved for cross-domain DTOs |
| Tests | Flat `tests/` | `unit/` (per-domain) + `integration/` + `e2e/` (reserved) |
| Health service testability | Bound to global engine | Injectable engine → real unit tests for DB-down path |
| Naming | — | `repository_intelligence` → `intelligence` (avoid collision with `repositories/`) |

## Why it changed (weaknesses found)

1. **W1 — Generic `services/` folder.** Sprint 3+ would dump GitHub, scanner,
   prediction, report services into one unrelated bucket. Fix: domains.
2. **W2 — Ambiguous schema ownership.** Contracts belong with their domain.
3. **W3 — No enforced boundaries.** Nothing stopped a future domain from
   importing another; dependency rules are now explicit and documented.
4. **W4 — No orchestration home.** The GitHub→…→Reports pipeline needs a
   composition point off the request path → `workers/`.
5. **W5 — Flat test layout.** Would not scale per domain → unit/integration/e2e.
6. **W6 — Health service untestable.** Global engine import → injectable engine.
7. **W7 — Naming collision.** `repository_intelligence` vs `repositories/` →
   `intelligence`.

## Benefits

- **Each domain is independently developable and testable** — a new sprint
  touches one domain package without disturbing others.
- **Dependency flow is explicit**: `api → workers → domains → core/db/models`,
  domains never import siblings. Violations are caught in code review and CI.
- **Tool swaps are non-breaking**: scanners, GitHub, and the future LLM sit
  behind domain ports (documented, ports to be defined with each sprint).
- **Test pyramid now visible**: unit tests with injected dependencies,
  integration tests against a live test DB, e2e reserved.
- **Cleaner naming**: `intelligence` eliminates the repositories collision.

## Future scalability

- **GitLab / Bitbucket / Azure DevOps**: implement the source-provider port
  that `domains/github/` will define in Sprint 3 — no downstream changes.
- **Kubernetes**: lands as analysis capability or a new domain, orchestrated
  like the rest.
- **Renovate**: adapter/domain under github/analysis, wired in `workers/`.
- **Prediction engine** (Sprint 7): isolated in `domains/prediction/` with its
  own tests; feature store fed by `domains/intelligence/`.

## Validation

- `ruff check` ✅ · `ruff format --check` ✅ · `pyright app tests` ✅
- `pytest` ✅ (10 tests: 4 unit health via the DatabaseProbe port + 3 health
  integration + 3 security integration)
- `alembic upgrade head` ✅ (fresh SQLite)
- Live `GET /api/v1/health` ✅ `{"status":"ok","database":"ok"}`
- Frontend build/lint/typecheck unaffected ✅

## Files created/modified

- Created: `app/domains/` (+ 9 domains), `app/workers/`, test layer structure,
  `docs/backend-structure.md`, `docs/domain-overview.md`,
  `docs/module-dependency.md`, this report.
- Domain code: `app/domains/health/` — `service.py` (typed against the
  `DatabaseProbe` port), `schemas.py`, `ports.py` (the port that makes the
  health domain the genuine reference implementation and the unit test
  cast-free).
- Modified: `app/api/routers/health.py` (imports), `app/main.py` (docstring),
  `app/schemas/__init__.py`, `app/repositories/__init__.py`,
  `docs/architecture.md`, `apps/backend/README.md`.
- Removed: `app/services/`, `app/schemas/health.py` (moved into domains).
