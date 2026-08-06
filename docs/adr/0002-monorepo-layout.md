# ADR 0002 — Monorepo with separately deployable apps

- **Status:** Accepted
- **Date:** 2026-08-03
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 1 project structure

## Context

EvoShield spans a Next.js frontend, a FastAPI backend, shared packages, docs
and CI. The target deployment (Render) can host each app independently. We need
one repository that keeps cross-cutting changes atomic and reviewable without
coupling the apps' lifecycles.

## Decision

- Use a **single git monorepo** with this layout:

```
apps/frontend   Next.js App Router (deployable unit)
apps/backend    FastAPI service (deployable unit)
packages/       Shared workspace packages (typed contracts, future SDKs)
docs/           Architecture, sprint plans, ADRs
research/       Tooling & approach research notes
scripts/        Root-level dev tooling
.github/        CI workflows
```

- Each `apps/*` folder owns its own `package.json` / `pyproject.toml`,
  lockfile, lint/test/build configuration, and README.
- Root `package.json` exposes orchestration scripts (`setup`, `dev`, `lint`,
  `test`, `build`) that delegate into the apps.
- Apps communicate only over HTTP (frontend → backend API). No direct import
  of app internals across `apps/*`.

## Consequences

- Independent deployment: Render builds frontend and backend from the same repo
  using per-app configuration.
- A single PR can touch frontend + backend + docs coherently (typical for
  cross-cutting features like auth).
- Slightly more tooling ceremony at the root than a polyrepo; the
  orchestration scripts keep it ergonomic.

## Alternatives considered

- **Polyrepo (one repo per app):** rejected — cross-cutting changes (auth,
  contracts) would need coordinated PRs across repositories and duplicated CI.
- **All-in-one app:** rejected — would couple React and Python lifecycles and
  complicate the Render deployment story.
