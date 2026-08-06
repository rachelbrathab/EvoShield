# packages/

Shared, versioned libraries reused across the monorepo.

> **Status (Sprint 1):** intentionally empty. We are NOT adopting workspace
> tooling yet — each app ships independently so CI stays fast and simple.
> See `docs/adr/0003-app-tooling.md`. In Sprint 12 (Optimization) we evaluate
> a pnpm + Turborepo workspace and migrate shared code here.

## Planned packages

| Package            | Contents                                             | Sprint |
| ------------------ | ---------------------------------------------------- | ------ |
| `@evoshield/ui`    | Shared shadcn/ui component library                   | 12     |
| `@evoshield/config`| Shared ESLint / TypeScript / Tailwind presets        | 12     |
| `@evoshield/client`| Typed API client generated from the OpenAPI contract | 8      |
| `@evoshield/contracts`| Cross-app types + feature flags                   | 12     |

**API contract note:** the single source of truth between frontend and backend
is the **OpenAPI schema** emitted by FastAPI (`/openapi.json`). The frontend
does not hand-maintain duplicated DTO types (see `docs/adr/0004-api-contract.md`).
