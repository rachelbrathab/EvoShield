# ADR 0001 — Database layer: Postgres-first with SQLite local fallback

- **Status:** Accepted
- **Date:** 2026-08-03
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 1 data layer setup

## Context

The production target is Supabase-managed PostgreSQL, but local development
must be frictionless for a single developer machine with no Docker available.
We need schema that behaves identically across both, migrations that run
everywhere, and a test suite that does not depend on a live Postgres instance.

## Decision

- Use **SQLAlchemy 2.0 async** as the single ORM/data-access layer.
- Use **`asyncpg`** as the Postgres driver (production / Supabase).
- Use **`aiosqlite`** as the zero-dependency local dev fallback.
- Default `DATABASE_URL` in dev is SQLite; production overrides via env var.
- All schema is **dialect-safe**:
  - UUID primary keys via `sqlalchemy.Uuid` (maps to `TEXT` on SQLite,
    `uuid` on Postgres).
  - No Postgres-only column types in shared models.
- **Alembic** owns schema evolution in both environments; migration files are
  generated once and run on any supported dialect.
- The engine pool is configured per dialect (`check_same_thread` for SQLite,
  quick connect timeouts for Postgres).

## Consequences

- Developers can run the whole stack with zero external services.
- The migration/ORM contract is verified against SQLite locally and against
  Postgres in CI (added in the testing sprint).
- Postgres-specific features (e.g. `jsonb`, partial indexes, `tsvector`) must
  be introduced deliberately and only when the product genuinely needs them.

## Alternatives considered

- **Docker Compose Postgres:** rejected — no Docker on the dev machine;
  adds startup friction for a single-owner project.
- **Supabase local CLI:** rejected — heavier tooling than needed for Sprint 1;
  re-evaluated in Sprint 2 when auth is wired.
