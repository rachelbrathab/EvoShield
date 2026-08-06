# ADR 0008 — Analysis domain: the orchestration layer for every future scanner

- **Status:** Accepted
- **Date:** 2026-08-06
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 4A — analysis infrastructure

## Context

EvoShield will run several independent security tools (Trivy, Syft, Grype,
Semgrep, Gitleaks), plus structure/manifest analysis and, later, automated
remediation and AI. If each tool owned its own run bookkeeping, the platform
would fragment: no consistent history, no uniform status vocabulary, no shared
cancellation or timeout behavior, and a UI that must special-case every
scanner.

We need one place that owns the *lifecycle of a run* — queueing, dispatch,
timing, outcomes, cancellation — while knowing nothing about what any scanner
does. Scanners must be pluggable without touching the API, the database, or
the UI.

## Decision

A new bounded context, `app/domains/analysis/`, owns the run lifecycle:

- **`AnalysisRun` aggregate** (`app/models/analysis_run.py`): one row per
  pipeline execution — repository, trigger, run-level status enum
  (`queued · running · completed · failed · cancelled`), started/completed
  timestamps, `duration_ms`, pipeline version, failure reason. The repository
  row keeps only the *latest* state (`analysis_status`,
  `last_analysis_at`, `last_analysis_job_id`), so history and current state
  are not duplicated.
- **`AnalysisProvider` port** (`ports.py`): `name`, `version`, `supports()`,
  `execute()`. The orchestrator depends only on this port. Sprint 4A ships
  one adapter — `FakeAnalysisProvider` — which simulates a run with a
  configurable delay, cancellation support, and an optional failure mode for
  validating the orchestration layer. Real scanners arrive in Sprint 5 as
  sibling adapters.
- **`AnalysisOrchestrator`** (`orchestrator.py`): the state machine. Creates
  runs, rejects duplicates, mirrors the repository lifecycle
  (queued → analyzing → analyzed/failed/not_analyzed), enforces a hard
  timeout, records timing, and cancels queued/running runs. Its only
  knowledge of execution is the port.
- **`factory.py`**: selects the provider from settings
  (`ANALYSIS_PROVIDER=fake` today; `trivy` etc. become valid values later).
  Unknown providers fail fast at DI time.
- **API**: six endpoints under `/api/v1` operating on `AnalysisRun` only —
  start (`POST /repositories/{id}/analysis`), history (`GET /analysis`,
  `GET /repositories/{id}/analysis`), detail (`GET /analysis/{id}`), cancel
  (`POST /analysis/{id}/cancel`), delete (`DELETE /analysis/{id}`).

Key state-transition rules:

```
QUEUED ──▶ RUNNING ──▶ COMPLETED
  │            │
  └──▶ CANCELLED ─┘     (queued or running)
                    RUNNING ──▶ FAILED   (provider error or timeout)
```

- Transitions are validated against an allow-list; a late write can never
  clobber a terminal state (cancelled/completed runs reject further
  transitions).
- Runs are owner-scoped through the repository row
  (`run → repository → owner`); a missing/foreign run is a 404.
- Cancel uses a per-run `asyncio.Event` the provider polls — cooperative
  cancellation, no worker required.
- Execution is an in-process asyncio task (the Sprint 4A simulation path).
  Sprint 5 replaces it with a real worker; the state machine, port and API
  do not change.

### Why the model lives in `app/models/` (not the domain folder)

The suggested structure placed `analysis/models.py` inside the domain, but
the project rule (ADR 0006, `docs/backend-structure.md`) makes `app/models/`
the single schema source Alembic autogenerates from. Splitting model files
across domains would fragment that source. The domain still owns everything
else about the aggregate — status, transitions, data access, contracts.

### Why no `workers.py` / `providers/interfaces/` / `utils/` placeholders

The sprint forbids placeholder code that is never used. Those folders ship
only when they hold real content (Sprint 5 worker, additional providers).

## Consequences

**Positive**

- Scanners are configuration, not code: adding Trivy is one adapter + a
  settings value; the API, database and UI are unchanged.
- The existing `AnalysisStatusBadge` (Sprint 3 prep) starts working for
  free: the orchestrator drives `Repository.analysis_status`.
- Uniform history (`analysis_runs`) gives the analysis page, reports and the
  prediction layer one consistent run timeline.
- Run-level and repository-level status are deliberately separate: a
  repository shows its latest state; each run keeps its own record.

**Trade-offs / notes**

- The fake provider's in-process task is a dev-simulation vehicle only; a
  multi-process deployment needs the Sprint 5 worker to own execution.
- `analysis_runs` carries no findings — Sprint 5 scanner tables own those.
- Token storage, encrypted-at-rest secrets, and worker durability are
  deferred to their dedicated sprints (ADR 0007, Sprint 12).

## Alternatives considered

- **Scanner-owned run tables** — rejected: no shared history or lifecycle;
  the UI and prediction layer would duplicate plumbing per tool.
- **A generic `jobs` table** — rejected: loses domain meaning and the
  repository lifecycle link; the analysis vocabulary (analyzed/failed)
  would be re-derived everywhere.
- **Orchestrator hard-wired to a fake** — rejected: the port is what makes
  Sprint 5 non-breaking; it costs one small interface now.
