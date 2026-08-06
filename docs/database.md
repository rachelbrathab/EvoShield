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

### `repositories`  *(Sprint 3 preparation)*

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
| `analysis_runs` | 4 | `analysis` | Per-run history: status transitions, artifact refs, scanner versions |
| `findings` | 5 | `scanners` | Normalized scan results (tool-agnostic) |
| `intelligence_*` | 6 | `intelligence` | Temporal risk features |
| `predictions` | 7 | `prediction` | Model outputs + confidence |
| `recommendations` | 8 | `recommendation` | Remediation guidance |

These are deliberately separate tables: scanners plug into the existing
`analysis_status` mechanism and never add columns to `repositories`.
