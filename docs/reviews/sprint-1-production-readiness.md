# Sprint 1 — Production Readiness Review

> **Date:** 2026-08-03
> **Reviewer:** Senior Staff Software Engineer (production readiness pass)
> **Scope:** entire repository as shipped at end of Sprint 1
> **Method:** manual code + config audit, cross-checked against CI, docs, and
> live behavior; fixes implemented and re-verified where they improve the
> architecture.

---

## Executive summary

Sprint 1 landed a clean, well-structured foundation: sound clean architecture
in the backend, a modern dark-first frontend, working CI, and good ADR
discipline. The review found **no critical or high-severity defects**. The
issues below are **medium/low severity hygiene and hardening gaps** typical of a
first sprint — most are now fixed in this pass.

The single most important gap was architectural: **the Postgres path — the
production database — was never exercised in CI**, despite `conftest.py`
documenting that it was. This is now fixed with a dedicated Postgres 16 CI job.

## Scorecard

| Area | Grade | Notes |
| --- | --- | --- |
| Folder structure | A | Clean monorepo, clear layer boundaries |
| Code organization | A− | SOLID-respecting; services/repositories empty but intentional |
| Naming | B+ | One generic package name fixed (`frontend` → `@evoshield/frontend`) |
| Architecture | A− | Postgres CI gap fixed; docs now match reality |
| Dependency management | B+ | `shadcn` CLI moved to devDependencies; types aligned to Node 24 |
| Environment configuration | B+ | `ALLOWED_HOSTS` + `NEXT_PUBLIC_APP_URL` added |
| Security | B+ | Host validation + security headers added; Dockerfile non-root |
| Performance | A− | Static landing page; async backend; no issues |
| Scalability | B | Postgres-first data layer validated in CI |
| Documentation | B+ | Boilerplate frontend README replaced; broken ADR links fixed |
| CI/CD | B+ | Postgres job + pyright added; concurrency + caches in place |
| Git practices | B+ | `.gitattributes` added; `.freebuff/` ignored |

## Findings

### F-01 — Production database never tested in CI (medium, fixed)
- **Problem:** `tests/conftest.py` documented that the Postgres path is
  exercised "in CI with a live service container", but the workflow had no
  Postgres job — only SQLite tests ran. The architecture's headline claim
  (Postgres-first, Supabase in prod) was unverified.
- **Impact:** dialect-specific breakage (UUID handling, migrations, pool
  config) would only surface at deployment. The review missed it because the
  docs described intent, not reality.
- **Solution:** added a `backend-postgres` job with a Postgres 16 service
  container that applies `alembic upgrade head` and runs the test suite.
  `conftest.py` now uses `os.environ.setdefault` so an explicit
  `DATABASE_URL` (from CI) wins over the SQLite default.
- **Status:** ✅ fixed.

### F-02 — No backend static type checking (medium, fixed)
- **Problem:** the frontend runs `tsc --noEmit` in CI, but the backend had no
  type checker at all — Python type hints were unenforced.
- **Impact:** type errors drift silently; the "typed end-to-end" claim in the
  README was aspirational.
- **Solution:** added `pyright` to the dev dependency group and a
  `uv run pyright app tests` step in CI.
- **Status:** ✅ fixed.

### F-03 — Host-header injection and missing security headers (medium, fixed)
- **Problem:** no `TrustedHostMiddleware` (Host-header poisoning / cache
  poisoning vectors) and no security response headers (nosniff, framing,
  referrer policy, HSTS).
- **Impact:** for a DevSecOps product, shipping without these is a credibility
  and security gap; browsers default to permissive behavior.
- **Solution:** new `app/core/security.py` adds host allowlisting
  (`ALLOWED_HOSTS` config) and sets `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and HSTS in production. Wired in `main.py`.
- **Status:** ✅ fixed.

### F-04 — Dockerfile ran as root with stale build approach (medium, fixed)
- **Problem:** `FROM python:3.12-slim` + `pip install .` runs the container as
  **root** with a full build in the runtime image; no healthcheck.
- **Impact:** container breakout from a compromised process escalates to host
  root; images are large and slow to build.
- **Solution:** multi-stage build (`ghcr.io/astral-sh/uv` builder → slim
  runtime), non-root `app` user, `uv sync --frozen --no-dev`, and a healthcheck
  against `/api/v1/health`.
- **Status:** ✅ fixed.

### F-05 — Boilerplate frontend README (low, fixed)
- **Problem:** `apps/frontend/README.md` was the untouched
  create-next-app template ("edit `app/page.tsx`", Vercel links).
- **Impact:** misleading for a real project; contradicts the professional
  documentation standard set elsewhere.
- **Solution:** replaced with a project-specific README (stack, layout, run,
  checks, config).
- **Status:** ✅ fixed.

### F-06 — Hardcoded `metadataBase` (low, fixed)
- **Problem:** `metadataBase: new URL("http://localhost:3000")` hardcoded in
  the root layout.
- **Impact:** OG/metadata URLs would point at localhost in production.
- **Solution:** driven by `NEXT_PUBLIC_APP_URL` (default localhost), documented
  in both env examples.
- **Status:** ✅ fixed.

### F-07 — Generic package name + misplaced CLI dependency (low, fixed)
- **Problem:** frontend package named `frontend`; `shadcn` (a build-time CLI)
  sat in `dependencies`; `@types/node@^20` mismatched Node 24.
- **Impact:** name collisions / unclear ownership in a monorepo; `shadcn` ships
  in production bundles of the lockfile; stale types.
- **Solution:** renamed to `@evoshield/frontend` (consistent with the planned
  `@evoshield/*` scope), moved `shadcn` to `devDependencies`, bumped
  `@types/node` to `^24`.
- **Status:** ✅ fixed.

### F-08 — `.freebuff/` app state not gitignored (low, fixed)
- **Problem:** `.freebuff/` (desktop app internal SQLite state, including
  `-shm`/`-wal` files) was untracked-but-unignored; `*.db` only matched the
  main file.
- **Impact:** risk of committing app-local state and multi-MB WAL files.
- **Solution:** explicit `.freebuff/` entry in `.gitignore`.
- **Status:** ✅ fixed.

### F-09 — Broken internal doc references (low, fixed)
- **Problem:** `packages/README.md` referenced `docs/adr/0002-app-tooling.md`
  and `0003-api-contract.md`, neither of which existed under those names.
- **Impact:** documentation dead-ends; readers can't find the rationale.
- **Solution:** wrote the missing ADRs (`0003-app-tooling`,
  `0004-api-contract`) and corrected the links.
- **Status:** ✅ fixed.

### F-10 — No `next output: standalone` (low, fixed)
- **Problem:** the Next.js config was empty; the default build requires
  `node_modules` at deploy time.
- **Impact:** complicates the Render/container deployment (Sprint 14) and
  bloats the image.
- **Solution:** `output: "standalone"` — self-contained server build.
- **Status:** ✅ fixed.

### F-11 — No line-ending normalization (low, fixed)
- **Problem:** no `.gitattributes`; mixed line endings could slip in across
  OSes.
- **Impact:** noisy diffs, broken `*.sh` on some checkouts.
- **Solution:** `.gitattributes` enforces LF (auto) and marks lockfiles/binary
  types.
- **Status:** ✅ fixed.

### F-12 — Upstream deprecation noise in tests (info, fixed)
- **Problem:** pytest printed a `StarletteDeprecationWarning` (TestClient via
  httpx).
- **Impact:** test output noise; no functional issue.
- **Solution:** scoped `filterwarnings` for `starlette.testclient`; revisit
  when the ecosystem settles (tracked in research notes).
- **Status:** ✅ fixed.

## Observations (no change required)

- `services/` and `repositories/` are intentionally empty — wiring lands with
  real features in Sprint 2+. The layering is already correct.
- CTA/hero links are placeholders (`href="#"`) — replaced by real routes when
  auth ships in Sprint 2.
- No frontend component tests yet — scheduled in the testing sprint (13),
  matching the roadmap.
- `DATABASE_URL` dev default is SQLite; production must override — documented
  in both env examples.

## Verification (post-fix)

- Backend: `ruff check` ✅, `ruff format --check` ✅, `pyright app tests` ✅
  (0 errors, config pinned to `basic`), `pytest` 6/6 ✅ (3 health + 3 new
  security-middleware tests), `alembic upgrade head` ✅ (SQLite).
- Frontend: `eslint` ✅, `tsc --noEmit` ✅, `next build` ✅ (standalone output).
- Live: frontend :3000 renders; backend `/api/v1/health` returns
  `{"status":"ok","database":"ok"}` with security headers applied and
  forged Host headers rejected (HTTP 400).

## Follow-ups

- Sprint 2 must land CSP headers once the app shell exists (noted in
  `security.py`).
- Re-run this review after Sprint 3 (GitHub OAuth) — auth is where the risk
  surface grows.
