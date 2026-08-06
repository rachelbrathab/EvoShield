# Sprint 4A — Analysis Infrastructure

> **Status:** ✅ Shipped — 2026-08-06

## Goal

Build the "operating system" for the analysis engine: the orchestration layer
every future security scanner (Trivy, Syft, Grype, Semgrep, Gitleaks) plugs
into — without running any real scan. A user can open a repository, click
**Run analysis**, watch a run move through `queued → running → completed`
(with a timeline), open the analysis history page, and cancel a queued run.

No scanner executes. No findings, no vulnerabilities, no background workers,
no AI, no prediction, no reports.

## Design decisions (explained before implementation)

1. **Model lives in `app/models/analysis_run.py`, not `domains/analysis/models.py`.**
   The established architecture (ADR 0006, `backend-structure.md`) makes
   `app/models/` the single schema source Alembic autogenerates from. The
   domain still owns everything else: port, orchestrator, data access,
   contracts.
2. **One state-machine owner.** The sprint's suggested `service.py` +
   `orchestrator.py` pair would alias each other; the sprint also bans unused
   placeholder code — so a single `orchestrator.py` owns all transitions.
3. **No empty placeholder folders.** `providers/interfaces/`, `workers.py`,
   `utils/` ship only when they hold real code (Sprint 5 worker, more
   providers).
4. **Repository lifecycle stays in lockstep.** The orchestrator flips
   `Repository.analysis_status` (queued → analyzing → analyzed/failed/
   not_analyzed) and stamps `last_analysis_at` + `last_analysis_job_id` on
   completion — the existing `AnalysisStatusBadge` on cards and detail pages
   starts working for free.
5. **Simulation is an in-process asyncio task, not a worker.** The queue hold
   + provider run live in a task spawned by the orchestrator with its own DB
   session. Cancellation is a per-run `asyncio.Event` the provider polls.
   Sprint 5 replaces the task with a real worker; the state machine, port and
   API do not change.
6. **Scanners plug in behind the `AnalysisProvider` port** (`name`, `version`,
   `supports()`, `execute()`); `factory.py` selects the provider from
   settings (`ANALYSIS_PROVIDER=fake` today). Adding Trivy later = one adapter
   + one settings value.
7. **Ownership derives through the repository row** (`run → repository →
   owner`); a missing or foreign run is a 404.

## State machine

```
QUEUED ──▶ RUNNING ──▶ COMPLETED
  │            │
  └──▶ CANCELLED ─┘     (queued or running)
              RUNNING ──▶ FAILED   (provider error or timeout)
```

- Transitions are validated against an allow-list; a late write can never
  clobber a terminal state.
- One active (queued/running) run per repository → `409` on duplicate start.
- Hard timeout via `asyncio.timeout`; elapsed time recorded as `duration_ms`.

## What changed

### Backend — `app/domains/analysis/` (new domain)

- **`models/analysis_run.py`** — `AnalysisRun` aggregate + `AnalysisRunStatus`
  enum (`queued · running · completed · failed · cancelled`, enum-as-VARCHAR
  like the repository status). Fields: `repository_id`, `triggered_by`,
  `status`, `started_at`, `completed_at`, `duration_ms`, `analysis_version`,
  `failure_reason`, timestamps.
- **Migration `0005_analysis_runs`** — `analysis_runs` table + indexes on
  `repository_id` and `status`.
- **`ports.py`** — `AnalysisProvider` port + `AnalysisExecutionContext`; the
  seam Sprint 5 scanners implement.
- **`providers/fake.py`** — `FakeAnalysisProvider`: simulated run with
  configurable delay, failure mode, and cooperative cancellation.
- **`factory.py`** — `build_analysis_provider()`; unknown provider names fail
  fast at DI time (`ANALYSIS_PROVIDER` in settings, default `fake`).
- **`orchestrator.py`** — `AnalysisOrchestrator`: create/validate/dispatch/
  complete/fail/cancel/delete, repo-lifecycle mirror, timeout, timing, and the
  in-process background simulation task (best-effort failure marking).
- **`repository.py`** — `AnalysisRunRepository`: owner-scoped run queries
  (`run → repository → owner` join), pagination + status/repo filters.
- **`schemas.py`** — `AnalysisRunRead` (with `repository_full_name` filled
  from the ownership join), list/create/cancel contracts.
- **Router** — six endpoints (below) registered via `get_analysis_orchestrator`
  DI dependency.

### API (all owner-scoped, operate on `AnalysisRun` only)

| Endpoint | Purpose |
| --- | --- |
| `POST /repositories/{id}/analysis` | Start a run (`201`; `409` if an active run exists) |
| `GET /analysis` | List the user's runs (page/page_size/repository_id/status) |
| `GET /repositories/{id}/analysis` | List runs for one repository |
| `GET /analysis/{id}` | Run detail (polled live by the UI) |
| `POST /analysis/{id}/cancel` | Cancel queued/running (`409` on terminal) |
| `DELETE /analysis/{id}` | Delete a terminal run (`409` on active) |

Errors: `404` missing/foreign, `409` duplicate-active / cancel-terminal /
delete-active, `500` provider unavailable (best-effort task failure marks the
run `failed`).

### Frontend

- **`lib/analysis.ts`** + **`lib/analysis-api.ts`** — run types, status
  metadata (label/color/step), and the typed API client.
- **`components/analysis/analysis-run-status-badge.tsx`** — per-run status
  badge; **`analysis-timeline.tsx`** — queued/running/completed visual
  timeline with timing and failure/cancelled outcomes.
- **`app/app/analysis/page.tsx`** — Analysis history page (paginated run
  list, status + repository filters).
- **`app/app/analysis/[id]/page.tsx`** — run detail with live polling
  (2 s while active) and the timeline.
- **`app/app/repositories/[id]/page.tsx`** — **Run analysis** button +
  recent-runs section on the repository detail page.
- **`app/app/layout.tsx`** — the Analysis nav item is now live.
- Pagination component generalized with an optional page-size selector
  (backward compatible; the repository list is unchanged).

### Testing

- **Backend:** 20 new tests (94 total) — `tests/unit/domains/analysis/
  test_orchestrator.py` (transitions, duplicate-start rejection, cancel,
  timeout, failure, stale-state protection) and `tests/integration/
  test_analysis_api.py` (endpoints, ownership 404s, duplicate 409, cancel,
  delete, live queued→running→completed simulation).
- **Frontend:** 14 new tests (72 total) — run-status metadata mapping,
  timeline rendering, plus pure `lib/analysis` helpers.

## Validation

### Post-review hardening (code review findings)

- **Duplicate-active-run protection is now DB-enforced.** The orchestrator's
  check-then-insert could race: two concurrent `POST /repositories/{id}/analysis`
  calls could both pass the "no active run" check and insert two `queued`
  rows. Added a **filtered unique index** on
  `analysis_runs(repository_id) WHERE status IN ('queued','running')` (model
  `__table_args__` + migration 0005; supported on both Postgres and SQLite)
  and the orchestrator converts the resulting `IntegrityError` into the
  documented `409 analysis_already_active` — the 409 contract is now atomic.
- **Cancel responses now include `repository_full_name`** (the orchestrator
  returns the run + name tuple like `start`/`get`), so the UI never loses the
  repository label after cancelling.
- Removed a dead-code ternary in the analysis detail page's back link.
- Frontend polling reviewed: interval cleared on unmount, polling stops at
  terminal states, initial fetch guards setState after unmount.

| Check | Result |
| --- | --- |
| Backend ruff (check + format) | ✅ clean |
| Backend pyright | ✅ 0 errors |
| Backend pytest — SQLite | ✅ 94 passed |
| Backend pytest — PostgreSQL 18 (fresh cluster, `alembic upgrade head`) | ✅ 94 passed |
| Frontend vitest | ✅ 72 passed |
| Frontend `tsc --noEmit` | ✅ 0 errors |
| Frontend eslint | ✅ 0 warnings |
| Frontend `next build` | ✅ green |

## Files

**Backend (new)**
- `app/models/analysis_run.py`, `alembic/versions/20260806_0005_analysis_runs.py`
- `app/domains/analysis/`: `ports.py`, `orchestrator.py`, `repository.py`,
  `schemas.py`, `factory.py`, `providers/fake.py`, `providers/__init__.py`,
  `__init__.py`
- `app/api/routers/analysis.py` (+ `app/api/router.py`, `app/api/deps.py`,
  `app/core/config.py`, `app/models/__init__.py`, `.env.example`)
- `tests/unit/domains/analysis/test_orchestrator.py`,
  `tests/integration/test_analysis_api.py`

**Frontend**
- `lib/analysis.ts`, `lib/analysis-api.ts`
- `components/analysis/`: `analysis-run-status-badge.tsx`,
  `analysis-timeline.tsx` (+ tests)
- `app/app/analysis/page.tsx`, `app/app/analysis/[id]/page.tsx`
- `app/app/repositories/[id]/page.tsx` (Run analysis + recent runs),
  `app/app/layout.tsx` (nav), `components/repositories/repository-pagination.tsx`
  (generalized), `test/fixtures.ts` (run fixture)

**Docs**
- `docs/adr/0008-analysis-domain.md` (new ADR — why scanners are isolated
  behind ports, how future providers plug in)
- `docs/backend-structure.md`, `docs/domain-overview.md`,
  `docs/module-dependency.md`, `docs/api.md` (6 endpoints), `docs/database.md`
  (`analysis_runs`), `docs/architecture.md` (roadmap), README roadmap
- This report

## Definition of done

A user can open a repository → **Run analysis** → see `queued → running →
completed` with a timeline → open the analysis history page → open a run's
detail page → cancel a queued analysis. No security findings exist yet.

**Awaiting approval before Sprint 4B** (real analysis on top of this
orchestration layer) — or Sprint 5 (scanner integration behind the
`AnalysisProvider` port).
