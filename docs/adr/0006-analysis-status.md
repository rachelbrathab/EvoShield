# ADR 0006 — First-class repository analysis status, before scanners exist

- **Status:** Accepted
- **Date:** 2026-08-06
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 3 preparation — repository analysis foundation

## Context

Sprints 4/5 will run analysis and security scans (Trivy, Syft, Grype, Semgrep,
Gitleaks) against repositories. Those pipelines are long-running background
jobs, so users must be able to see, at a glance, where each repository stands:
not analyzed, queued, running, done, failed, cancelled.

We are introducing this concept *now*, before the `repositories` table exists
(Sprint 3 creates ingestion) and long before any scanner runs, so that:

- Sprint 3's repository ingestion and Sprint 4/5's analysis pipeline both
  integrate against a stable, already-migrated schema — no database or UI
  redesign when scanning lands.
- The status vocabulary is fixed early, and the frontend badge rendering is
  ready to be dropped into repository cards and detail pages.

## Decision

- **Status lives on the `repositories` table as a scalar column**, not in a
  separate table. A repository has exactly one *current* analysis state at any
  moment; a column is the normalized representation of "current state".
  Per-run *history* (timestamps, scanner versions, artifact references) will
  be a separate `analysis_runs` table owned by the `analysis` domain in
  Sprint 4+ — the column only mirrors the latest run's outcome, so nothing is
  duplicated.
- **`AnalysisStatus` is a Python `StrEnum`** (`app/models/repository.py`)
  with `not_analyzed | queued | analyzing | analyzed | failed | cancelled`.
  Values are the canonical wire format (lowercase snake_case).
- **The column is a plain VARCHAR, not a DB enum.** `sa.Enum(..., native_enum=False,
  create_constraint=False)` stores strings and omits the database CHECK
  constraint. New states are added as new Python members **without a schema
  migration**, while `validate_strings=True` still rejects free-form strings
  at the model boundary and Pydantic rejects them at the API contract boundary.
- **`values_callable` maps members to their values** so the DB stores
  `"not_analyzed"` (not the member name `"NOT_ANALYZED"`), matching the
  migration's `server_default` and the API wire format.
- **Companion columns:** `last_analysis_at` (nullable timestamp of the most
  recent run) and `last_analysis_job_id` (nullable opaque worker/queue job id,
  kept as a string so any job system fits). Scan-specific data (SBOMs,
  findings, vulnerabilities) deliberately does **not** live on this table.
- **API contract:** `RepositoryRead` (`app/domains/github/schemas.py`)
  exposes the status trio via `from_attributes=True`. No repository endpoints
  exist yet (Sprint 3); the contract is ready for list/detail endpoints.
- **Frontend:** `lib/repository.ts` defines the status union + metadata, and
  `AnalysisStatusBadge` renders the placeholder badge (colored dot + label)
  that Sprint 3 repository cards reuse.

## Implementation notes

- **The column is `VARCHAR(32)`** (explicit `length=32` on both the model and
  the migration — `sa.Enum(native_enum=False)` would otherwise default to 255).
- **Hand-write migrations for this column.** `alembic revision --autogenerate`
  cannot reproduce the model's `values_callable` lambda and has no knowledge
  of the column's `server_default`, so it would emit a spurious alter for
  `analysis_status`. Keep this migration hand-written (the project convention)
  and never let autogenerate "fix" this column.
- **`RepositoryRead` uses `from_attributes=True`.** This is a deliberate,
  contract-only deviation from the "explicit mappers live in repositories"
  rule: with no endpoints yet, the schema is the ready-made wire contract.
  If Sprint 3 repository endpoints grow ORM-serialization as a habit, revisit
  with repository-level mappers.

## Consequences

- Sprint 3 and 4/5 pipelines only ever **update three columns** on the
  repository row to report lifecycle progress — no schema churn when analysis
  lands.
- The vocabulary is stable and shared: backend enum, OpenAPI contract and
  frontend badge all agree on the same six values.
- Adding a state later (e.g. `paused`) is one enum member + one metadata
  entry; the DB column needs no change.
- New scanner tools in Sprint 5 plug into the same status transitions; they
  never touch the repository model (findings get their own tables).

## Alternatives considered

- **Status as a separate table now:** rejected — a one-row-per-repo table
  with a single current value is denormalization with extra joins and no
  benefit; history belongs in the future `analysis_runs` table, not today.
- **Native Postgres enum:** rejected — breaks the SQLite-tolerant rule
  (ADR 0001) and adding states requires a migration + new enum type on both
  dialects.
- **Free-form string column:** rejected — no validation anywhere; typos
  would silently corrupt status and break UI rendering.
- **Store member names (`NOT_ANALYZED`):** rejected — inconsistent with the
  lowercase API vocabulary and the migration default; `values_callable` keeps
  one canonical representation.
