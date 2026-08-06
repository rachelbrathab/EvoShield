# EvoShield Database

> Companion to `docs/architecture.md` §5 (Data layer) and ADR 0001.
> This is the living catalog of every table, keyed to the Alembic migrations
> in `apps/backend/alembic/versions/`.

## Stack & rules

- **Postgres-first, SQLite-tolerant** (ADR 0001): production targets
  Supabase-managed Postgres (asyncpg); local dev and tests use SQLite
  (aiosqlite) with zero external services. All models, migrations and queries
  are dialect-safe.
- **Schema changes only via Alembic migrations** — never by hand. `models/`
  is the single ORM source of truth; the test suite rebuilds the schema from
  `Base.metadata`, which stays identical to `alembic upgrade head`.
- **UUID primary keys** everywhere (`uuid` type — native on Postgres,
  portable text on SQLite). Timestamps are timezone-aware with
  `created_at`/`updated_at` bookkeeping.

## Migration history

| Migration | Sprint | Purpose |
| --- | --- | --- |
| `0001_create_users` | 1 | `users` table (application profiles) |
| `0002_auth_identity` | 2 | Auth provider linkage on `users` + `auth_credentials` (local-provider revocation) |
| `0003_repository_analysis_status` | 3 prep | `repositories` table with first-class analysis status |
| `0004_repository_integration` | 3A | `provider_tokens` table + GitHub metadata columns on `repositories` |
| `0005_analysis_runs` | 4A | `analysis_runs` table — per-repository run history (status, timing, version, failure reason) |

## Tables

### `users`

Application-side user profiles. Authentication itself is delegated to an
auth provider (Supabase in production, local provider in dev) — see
`docs/adr/0005-identity-auth.md`.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Mirrors the auth identity UUID (deterministic per provider subject) |
| `email` | varchar(320) | Unique, indexed |
| `full_name` | varchar(255) | Nullable |
| `avatar_url` | varchar(2048) | Nullable |
| `is_active` | boolean | Default true |
| `auth_provider` | varchar(32) | `local` / `supabase` / `github` |
| `auth_provider_sub` | varchar(255) | Provider subject id, indexed |
| `last_login_at` | timestamptz | Nullable |
| `created_at` / `updated_at` | timestamptz | Bookkeeping |

### `auth_credentials`

Local-provider password hashes (Argon2id). Supabase-backed deployments never
populate this table.

| Column | Type | Notes |
| --- | --- | --- |
| `user_id` | uuid PK, FK → `users.id` | `ON DELETE CASCADE` |
| `password_hash` | varchar(255) | Argon2id hash |
| `created_at` / `updated_at` | timestamptz | Bookkeeping |

### `provider_tokens`  *(Sprint 3A)*

Per-user upstream access tokens — GitHub now, GitLab/Bitbucket later.
Written by the identity domain during the GitHub OAuth callback, read by
the `github` domain to call the GitHub API as the user.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `user_id` | uuid, FK → `users.id` | `ON DELETE CASCADE`, indexed |
| `provider` | varchar(32) | `github` (or later providers), indexed |
| `access_token` | varchar(512) | Plain text in dev; encrypt at rest in production (Sprint 12) |
| `token_type` | varchar(32) | `bearer` |
| `scope` | varchar(512) | OAuth scopes granted, e.g. `read:user user:email repo` |
| `expires_at` | timestamptz | Nullable (GitHub tokens don't expire today) |
| `created_at` / `updated_at` | timestamptz | Bookkeeping |

Constraint: `UNIQUE (user_id, provider)` — one token per provider per user.

### `analysis_runs`  *(Sprint 4A)*

The execution history of the analysis pipeline: one repository → many runs.
Owned by the `analysis` domain (see `docs/adr/0008-analysis-domain.md`). It
tracks only the run *lifecycle* — status transitions, timing, pipeline version
and failure reason. **No findings or vulnerabilities**: scanner results get
their own tables in Sprint 5. The `repositories` row keeps the *latest*
state (`analysis_status`, `last_analysis_at`, `last_analysis_job_id`), so
history and current state are deliberately not duplicated.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `repository_id` | uuid, FK → `repositories.id` | `ON DELETE CASCADE`, indexed |
| `triggered_by` | varchar(32) | `user` today; future automation (Renovate, schedules) sets its own value |
| `status` | varchar(16) | **Enum-as-VARCHAR** — `queued · running · completed · failed · cancelled`, indexed, default `queued` |
| `started_at` | timestamptz | Set when the run dispatches |
| `completed_at` | timestamptz | Set on terminal state |
| `duration_ms` | integer | Whole-run wall clock, set on terminal |
| `analysis_version` | varchar(32) | Pipeline version that executed (providers bump this), default `0.1.0` |
| `failure_reason` | varchar(512) | Human-readable reason for a failed run, nullable |
| `created_at` / `updated_at` | timestamptz | Bookkeeping |

`status` follows the same enum-as-VARCHAR pattern as `repositories.analysis_status`
(`sa.Enum(native_enum=False, create_constraint=False)` storing lowercase
`AnalysisRunStatus` values, validated in Python) — new run states are
code-only additions with no migration. Constraints are enforced by the
orchestrator state machine: a terminal run can never be overwritten by a late
write, and cancel/delete reject active runs.

### `repositories`  *(Sprint 3 preparation + 3A metadata)*

Provider-agnostic source-repository aggregate. Carries exactly one *current*
analysis state per repository; per-run history belongs to a future
`analysis_runs` table (Sprint 4+), so nothing is duplicated.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `owner_id` | uuid, FK → `users.id` | `ON DELETE CASCADE`, indexed |
| `provider` | varchar(32) | `github` default; GitLab/Bitbucket/Azure DevOps later |
| `provider_repo_id` | varchar(64) | Upstream id (e.g. GitHub numeric repo id), indexed, nullable until Sprint 3 ingestion |
| `name` | varchar(255) | Short name |
| `full_name` | varchar(512) | `owner/name` natural key, indexed |
| `default_branch` | varchar(255) | Nullable |
| `html_url` | varchar(2048) | Nullable |
| `description` | varchar(1024) | Nullable |
| `is_private` | boolean | Default false |
| `is_active` | boolean | Default true |
| `language` | varchar(64) | GitHub primary language, nullable (Sprint 3A) |
| `stars` | integer | Default 0 |
| `forks` | integer | Default 0 |
| `open_issues` | integer | Default 0 |
| `topics` | json | List of topic strings (JSONB on Postgres, TEXT on SQLite) |
| `license` | varchar(128) | SPDX id, e.g. `MIT` |
| `size_kb` | bigint | GitHub `size` in KiB |
| `archived` | boolean | Default false |
| `disabled` | boolean | Default false |
| `provider_created_at` | timestamptz | Upstream created timestamp |
| `provider_updated_at` | timestamptz | Upstream updated timestamp |
| `pushed_at` | timestamptz | GitHub `pushed_at` — what cards show as “last updated”, indexed |
| `last_synced_at` | timestamptz | When we last refreshed from the provider |
| `analysis_status` | varchar(32) | **Enum-as-VARCHAR** — see below, indexed, default `not_analyzed` |
| `last_analysis_at` | timestamptz | Most recent run's completion/start time, nullable |
| `last_analysis_job_id` | varchar(64) | Opaque worker/queue job id, nullable |
| `created_at` / `updated_at` | timestamptz | Bookkeeping |

Constraints:

- `UNIQUE (owner_id, full_name)` — one repository row per owner per repo.
- Indexes on `owner_id`, `provider`, `provider_repo_id`, `full_name`,
  `analysis_status`.

#### Why `analysis_status` is a VARCHAR, not a DB enum

The column stores the lowercase `AnalysisStatus` values
(`not_analyzed`, `queued`, `analyzing`, `analyzed`, `failed`, `cancelled`)
as plain strings — `sa.Enum(native_enum=False, create_constraint=False)`
emits no CHECK constraint. Validation happens in Python: SQLAlchemy's
`validate_strings=True` rejects unknown values at the model boundary, and
Pydantic rejects them at the API contract boundary. New states are added as
Python `StrEnum` members **without a schema migration**, and the same code
works on both Postgres and SQLite. See `docs/adr/0006-analysis-status.md`.

## Future tables (owned by later sprints)

| Table | Sprint | Owner domain | Purpose |
| --- | --- | --- | --- |
| `findings` | 5 | `scanners` | Normalized scan results (tool-agnostic) |
| `intelligence_*` | 6 | `intelligence` | Temporal risk features |
| `predictions` | 7 | `prediction` | Model outputs + confidence |
| `recommendations` | 8 | `recommendation` | Remediation guidance |

These are deliberately separate tables: scanners plug into the existing
`analysis_status` mechanism and never add columns to `repositories`.
