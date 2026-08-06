# Sprint 1 — Project Setup

> **Status:** ✅ Shipped — 2026-08-03

## Goal

Stand up a production-ready monorepo skeleton for EvoShield: a Next.js frontend
and FastAPI backend that run locally end-to-end, a dark-first landing page, a
green CI pipeline, and a documented architecture every later sprint builds on.

## Features

- Git repo + full monorepo layout (`apps/`, `packages/`, `docs/`, `research/`,
  `scripts/`, `.github/`, `.vscode/`)
- Next.js 16 + React 19 + TypeScript + Tailwind v4 + shadcn/ui (Base UI) with
  a dark-first design-token theme
- Professional landing page (hero with product mock, features, how-it-works,
  security stack, CTA) with a live API health badge
- FastAPI backend with clean architecture (api → services → repositories →
  models), async SQLAlchemy, Alembic migrations
- Health endpoint `/api/v1/health` reporting version, environment and DB state
- Local SQLite dev database with Postgres-first dialect-safe models
- Root tooling: `npm run setup`, `npm run dev`, lint/typecheck/test/build
  orchestration
- CI workflow (GitHub Actions): frontend lint/typecheck/build + backend
  ruff/pytest/migrations

## Folder structure (created)

```
evoshield/
├── apps/
│   ├── frontend/   Next.js App Router app
│   └── backend/    FastAPI service (uv-managed, Python 3.12)
├── packages/       workspace packages placeholder
├── docs/
│   ├── adr/        0001-database-layer, 0002-monorepo-layout
│   ├── architecture.md
│   └── sprint-plans/
├── research/       research notes
├── scripts/        setup.sh, dev.sh
├── .github/workflows/  ci.yml
├── .editorconfig  .env.example  .gitignore  .nvmrc  .vscode/
└── package.json (root orchestration)
```

## Backend files

```
apps/backend/
├── pyproject.toml          deps (fastapi, uvicorn, pydantic, sqlalchemy,
│                           asyncpg, aiosqlite, alembic) + dev (pytest, ruff)
├── .python-version         uv-managed Python 3.12
├── Dockerfile
├── alembic.ini / alembic/  migration env + versions/0001 users table
├── app/
│   ├── main.py             app factory (composition only)
│   ├── core/               config.py, logging.py, exceptions.py
│   ├── api/                router.py, deps.py, routers/health.py
│   ├── schemas/            health.py
│   ├── services/           health_service.py
│   ├── repositories/       (empty, Sprint 2+)
│   ├── models/             base.py, user.py
│   ├── db/                 session.py
│   └── utils/
└── tests/                  conftest.py, test_health.py
```

## Frontend files

```
apps/frontend/src/
├── app/
│   ├── layout.tsx          fonts, metadata, ThemeProvider, Toaster
│   ├── page.tsx            landing page composition
│   ├── globals.css         dark-first design tokens + utilities
│   └── icon.svg
├── components/
│   ├── ui/                 shadcn primitives (button, card, badge, …)
│   └── site/               header, footer, hero, features, how-it-works,
│                           security-stack, cta-section, risk-chart,
│                           health-badge, logo, github-icon
└── lib/
    ├── utils.ts            cn() helper
    └── api.ts              API client (health contract)
```

## Database changes

- Migration `0001` creates the `users` table (id UUID pk, email unique,
  timestamps, soft-delete) — dialect-safe for Postgres and SQLite.
- Dev default: `sqlite+aiosqlite:///./evoshield-dev.db` (zero setup).
- Prod override: `DATABASE_URL` → Supabase Postgres via `asyncpg`.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Service banner (`{name, docs}`) |
| GET | `/api/v1/health` | Status, version, environment, DB connectivity |
| GET | `/docs` | Swagger UI (dev only) |

## Frontend pages

- **`/`** — landing page (dark theme, fully responsive, health badge in header).

## Backend services

- `health_service.py` — pings the DB session, returns `HealthPayload`.

## Acceptance criteria

- [x] `npm run setup` completes without errors on a clean checkout
- [x] `npm run dev` starts frontend (:3000) and backend (:8000)
- [x] Landing page renders with the dark theme and a live API health badge
- [x] `GET /api/v1/health` returns `status: ok` with DB `ok`
- [x] `npm run lint` + `tsc --noEmit` + `next build` pass
- [x] Backend `ruff check`, `ruff format --check`, `pytest` pass
- [x] `alembic upgrade head` applies cleanly on a fresh database
- [x] CI workflow exists and mirrors the local checks

## Testing strategy

- Backend: pytest with a SQLite test database (in-memory override of
  `DATABASE_URL`), async client via httpx/ASGITransport.
- Frontend: lint + typecheck + production build (component tests arrive in the
  testing sprint, per roadmap).
- Manual smoke: dev servers, health badge flips online/offline with backend.

## Out of scope (next sprints)

- Authentication (Sprint 2), GitHub OAuth (Sprint 3), scanner orchestration
  (Sprint 5), prediction engine (Sprint 7), Recharts dashboard (Sprint 8).
