# ADR 0003 — App tooling: no workspace orchestration (yet)

- **Status:** Accepted
- **Date:** 2026-08-03
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 1 project structure

## Context

The monorepo has two independently deployable apps (Next.js + FastAPI) plus
future shared packages. Workspace tools (pnpm workspaces, Turborepo, Nx) could
orchestrate task running and caching, but add configuration surface and a
second lockfile regime.

## Decision

- Each app owns its **own lockfile** (`package-lock.json`, `uv.lock`) and its
  own lint/test/build scripts.
- The **root `package.json` delegates** to app scripts (`npm run setup`,
  `npm run dev`, `npm run lint`, …) — no cross-app task runner in Sprint 1.
- `packages/` stays empty until there is real shared code to justify a
  workspace migration.

## Consequences

- CI is simple and fast: two independent jobs with per-app caches.
- App lifecycle decoupling is preserved (Render can build each app from the
  same repo).
- Re-evaluated in Sprint 12 (Optimization): pnpm + Turborepo workspace if
  shared packages and caching become a bottleneck.

## Alternatives considered

- **pnpm workspaces + Turborepo from day one:** rejected — adds tooling
  ceremony before shared code exists; migration cost is low later.
- **npm workspaces:** rejected — hoisting quirks with a Python sibling app;
  no meaningful win today.
