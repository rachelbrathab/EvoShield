# Sprint 3 Preparation — Repository Analysis Status Foundation

> **Status:** ✅ Shipped — 2026-08-06

## Goal

Introduce a first-class **repository analysis status** concept into the
architecture *before* any repository ingestion or scanner exists, so Sprint 3
(GitHub integration) and Sprint 4/5 (analysis + scanners) integrate against a
stable, already-migrated schema — no database or UI redesign when scanning
lands.

Explicitly **not** included: GitHub integration, scanning, background
workers, analysis jobs, Trivy/Syft/Grype/Semgrep/Gitleaks, and any new
endpoints.

## Design decisions

1. **Status lives on the `repositories` table, as a scalar column.** A
   repository has exactly one *current* analysis state; a column is the
   normalized representation. Per-run *history* belongs to a future
   `analysis_runs` table owned by the `analysis` domain (Sprint 4+), so the
   column only mirrors the latest run — no duplication. See
   `docs/adr/0006-analysis-status.md`.
2. **`AnalysisStatus` is a Python `StrEnum`** (`app/models/repository.py`):
   `not_analyzed · queued · analyzing · analyzed · failed · cancelled`.
3. **Enum-as-VARCHAR, no DB CHECK.** `sa.Enum(native_enum=False,
   create_constraint=False)` + `validate_strings=True` + `values_callable` —
   new states are code-only additions (no migration), invalid values are
   rejected at both the model and the Pydantic contract boundary, and the
   column works identically on Postgres and SQLite.
4. **Scan-specific data never touches `repositories`.** Sprint 5 scanners
   report progress by flipping `analysis_status` and write findings to their
   own tables.
5. **Contract-first.** `RepositoryRead` (`app/domains/github/schemas.py`)
   exposes the status trio; the frontend `AnalysisStatusBadge` is ready for
   repository cards. No endpoints were added (Sprint 3).

## Features

- `AnalysisStatus` lifecycle enum (extensible without migration)
- `repositories` table: provider-agnostic identity + the status trio
  (`analysis_status`, `last_analysis_at`, `last_analysis_job_id`)
- `RepositoryRead` API contract exposing the status (no new endpoints)
- Frontend status vocabulary + placeholder `AnalysisStatusBadge`
  (⚪ Not Analyzed · 🟡 Queued · 🔵 Analyzing · 🟢 Analyzed · 🔴 Failed ·
  Cancelled)
- Dashboard status legend previewing the vocabulary

## Files created / changed

```
apps/backend/app/
├── models/
│   └── repository.py              NEW AnalysisStatus StrEnum + Repository aggregate
├── domains/github/
│   └── schemas.py                 NEW RepositoryRead contract (from_attributes)
apps/backend/alembic/versions/20260806_0003_repository_analysis_status.py   migration 0003
apps/backend/tests/
├── unit/domains/github/test_analysis_status.py   enum contract (4 tests)
└── integration/test_repository.py                lifecycle + uniqueness + rejection (3 tests)
apps/frontend/src/
├── lib/repository.ts                             AnalysisStatus union, Repository type, status metadata
├── components/repositories/analysis-status-badge.tsx   placeholder badge
└── app/app/page.tsx                              status legend card + stage bump
docs/
├── adr/0006-analysis-status.md                   NEW decision record
├── database.md                                   NEW schema catalog
├── architecture.md · domain-overview.md · backend-structure.md   updated
└── sprint-plans/003-analysis-status-foundation.md   this report
```

## Database changes

Migration `0003` (dialect-safe for Postgres + SQLite):

- New `repositories` table: `id` uuid pk; `owner_id` FK → `users.id`
  (CASCADE); `provider` (default `github`); `provider_repo_id` (nullable,
  indexed); `name`, `full_name` (indexed); `default_branch`, `html_url`,
  `description` (nullable); `is_private`, `is_active`; **`analysis_status`**
  (VARCHAR-backed enum, default `not_analyzed`, indexed); `last_analysis_at`
  (nullable); `last_analysis_job_id` (nullable); timestamps.
- `UNIQUE (owner_id, full_name)` — one row per owner per repo.
- Indexes: `owner_id`, `provider`, `provider_repo_id`, `full_name`,
  `analysis_status`.

## Acceptance criteria

- [x] `AnalysisStatus` enum defines all six states; unknown values rejected
- [x] New repositories default to `NOT_ANALYZED` with null run info
- [x] Status transitions persist and round-trip through `RepositoryRead`
- [x] Duplicate `(owner_id, full_name)` rejected at the DB
- [x] Migration 0003 applies cleanly on the dev DB (`alembic upgrade head`)
- [x] No repository endpoints, scanners, workers or analysis jobs added
- [x] Backend: `ruff check`, `ruff format --check`, `pyright` (0 errors),
  `pytest` — 43 passed (36 existing + 7 new)
- [x] Frontend: `eslint`, `tsc --noEmit`, `next build` all pass

## Implementation report

**What changed.** A `repositories` table with a first-class
`analysis_status` lifecycle (enum-backed, extensible, validated), the
`RepositoryRead` API contract, a frontend status vocabulary + placeholder
badge, migration `0003`, ADR 0006, and updated architecture/database/domain
docs.

**Why it was added now.** The analysis pipeline (Sprint 4/5) and repository
ingestion (Sprint 3) are the two features that would otherwise each invent
their own status mechanism — one as DB columns, one as UI badges — and force
a redesign when they met. Fixing the vocabulary, the schema and the badge
rendering *first* means both integrate against one stable contract.

**How it benefits Sprint 4.** Analysis jobs transition
`Repository.analysis_status` through the queue lifecycle and stamp
`last_analysis_at`/`last_analysis_job_id` — three existing columns, zero
schema churn. Scanner results (Trivy/Syft/Grype/Semgrep/Gitleaks) get their
own `findings` tables in Sprint 5 and never alter the repository model.
Repository cards and detail pages render the status with the badge that
already exists. Adding GitLab/Bitbucket later only touches the `provider`
value and the Sprint 3 source-provider port.
