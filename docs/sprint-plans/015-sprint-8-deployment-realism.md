# Sprint 8 — Deployment Realism & Cleanup

## Status

✅ Complete

## Objective

Make EvoShield **actually deployable and demoable** and remove everything
that misrepresents the project's state. After Sprint 7 the detection,
intelligence and remediation pipeline was functionally complete, but:

1. the shipped backend image contained **no scanner binaries and no git** —
   a `docker run` of the image could not perform a single scan;
2. a server restart permanently **stranded** queued/running analysis runs
   (their in-process asyncio tasks die with the process), deadlocking the
   repository behind the DB-level single-active-run guard;
3. the codebase and UI still advertised cancelled scope (empty `prediction`,
   `chat`, `recommendation`, `reports` domain stubs; "Coming soon" dashboard
   cards — one linking to a route that does not exist).

No new product features were added. This sprint closes the gap between
"works on the developer's machine" and "works as a deployed product".

## What was built

### 1. Scanner-bundled backend image (`apps/backend/Dockerfile`)

Rewritten to ship the full toolchain, with build-time verification
(`--version` for every binary fails the build on a broken layer):

| Tool | Version | Source |
| --- | --- | --- |
| Trivy | 0.74.0 | GitHub release tarball (linux/amd64) |
| Gitleaks | 8.30.1 | GitHub release tarball (linux/amd64) |
| Syft | 1.51.1 | GitHub release tarball (linux/amd64) |
| Grype | 0.118.0 | GitHub release tarball (linux/amd64) |
| Semgrep | 1.176.1 | PyPI, isolated venv symlinked into `/usr/local/bin` |

Also added: `git` + `ca-certificates` (repository acquisition), `curl`
(healthcheck/TLS), `libgcc-s1` (Go binaries), `procps` (subprocess cleanup),
writable pre-owned volume mount points for the scanner DB cache and the
repository-clone workspace, and an `ENTRYPOINT` so compose can run one-off
commands without duplicating image logic. Versions are `ARG`s — bump
deliberately, re-verify the release URL, re-run a real scan.

### 2. Stranded-run recovery (the "reaper")

- `app/domains/analysis/reaper.py` — `recover_stranded_runs()`: every
  queued/running run → FAILED with an explanatory `failure_reason`,
  PENDING/RUNNING scanner runs → FAILED, repositories stuck in
  `queued`/`analyzing` → `failed`. Terminal runs and terminal repository
  states are never touched.
- Wired into the FastAPI **lifespan** (`app/main.py`) behind
  `REAPER_ENABLED=true` (default). Recovery failure is logged, never fatal.
- `python -m app.cli recover-runs` — one-off command for multi-worker
  deployments (compose's `migrate` service runs it after
  `alembic upgrade head`).
- Deliberately **not** auto-re-queueing: scans need fresh clone acquisition
  and operator intent. Recovered runs are simply re-startable.

### 3. Frontend container + one-command stack

- `apps/frontend/Dockerfile` — standalone Next.js build (the config already
  used `output: "standalone"`), non-root, healthcheck; `NEXT_PUBLIC_API_URL`
  is a build arg because it is inlined into the client bundle.
- `docker-compose.yml` — `db` (postgres:16-alpine) + `migrate` (migrations +
  recovery, one-off) + `backend` (scanners, env-hardened: required
  `SESSION_JWT_SECRET`, scanner cache + workspace volumes) + `frontend`.
- `.env.compose.example` — documented template; the compose file fails fast
  if the session secret is missing.

### 4. Dead-code removal

- Deleted empty domain stubs `prediction/`, `chat/`, `recommendation/`,
  `reports/` (zero imports, zero routes — cancelled Sprint 8–10 scope).
- Dashboard rewritten: "Coming soon" cards (including a link to the
  non-existent `/app/predictions`) replaced with the three live capabilities;
  sidebar "Insights" section and the dead `Settings` link removed.

## Architecture decisions

- Recovery is a **startup concern with an explicit CLI twin** (ADR 0017):
  single-process deployments recover in the lifespan hook; multi-worker
  deployments run `recover-runs` once from the migrate/entrypoint job. No
  new tables, no scheduler, no worker infrastructure.
- Scanner toolchain is **baked into the image, pinned by ARG** rather than
  installed at runtime — reproducible, offline-capable after build, and
  verified at build time.
- Compose models the **production shape** (separate migrate job, healthcheck
  gates, named volumes for advisory-DB caches) instead of a dev-only toy.

## Files changed

```
apps/backend/Dockerfile                              rewritten (scanner toolchain)
apps/backend/app/domains/analysis/reaper.py          new — stranded-run recovery
apps/backend/app/cli.py                              new — ops CLI (recover-runs)
apps/backend/app/main.py                             lifespan hook + description fix
apps/backend/app/core/config.py                      reaper_enabled setting
apps/backend/app/domains/scanners/scanner_run_repository.py
                                                     naive-datetime duration fix (latent bug found by reaper tests)
apps/backend/tests/unit/domains/analysis/test_reaper.py  new — 4 tests
apps/frontend/Dockerfile                             new
apps/frontend/src/app/app/page.tsx                   dashboard rewrite
apps/frontend/src/app/app/layout.tsx                 nav cleanup
docker-compose.yml                                   new
.env.compose.example                                 new (+ .gitignore negation so the template is tracked)
.gitignore                                           track .env.compose.example despite the .env.* rule
docs/sprint-plans/015-sprint-8-deployment-realism.md new (this file)
docs/adr/0017-deployment-realism.md                  new
docs/backend-structure.md / docs/domain-overview.md  dead domains removed, reaper documented
README.md / apps/backend/README.md                   roadmap, docker quick start, layout sync
```

## Validation

Static + unit:

- `ruff format --check`: 162 files clean
- `ruff check`: all checks passed
- `pyright app tests`: 0 errors, 0 warnings
- `pytest`: **442 passed** (438 prior + 4 reaper tests), 4 warnings
  (pre-existing Starlette deprecation warnings)
- `npm run lint` / `tsc --noEmit`: clean
- `vitest run`: **72 passed** (12 files)
- `npm run build`: successful (standalone output)
- `docker compose config`: valid

Live smoke test (Docker Desktop, engine 29.7.2, full `compose up --build`):

- Both images build; all four scanners answer `--version` **inside the
  running container as the non-root user**: Trivy 0.74.0, Gitleaks 8.30.1,
  Semgrep 1.176.1, Syft 1.51.1, Grype 0.118.0, git 2.47.3.
- `migrate` applies all 8 migrations on PostgreSQL 16, then recovery runs.
- `/api/v1/health` → 200 `ok`, `database: ok`, `environment: production`.
- Frontend serves on :3000 (login page 200).
- **Real scanner execution proven**: Gitleaks run against a planted secret
  file inside the container produced 1 finding (`generic-api-key`); the
  secret value appears only in the transient raw report file — never stored
  (the parser redaction layer is unchanged).
- **Recovery proven end-to-end**: a stranded RUNNING run planted in the
  compose PostgreSQL → `python -m app.cli recover-runs` → run FAILED with
  reason, repository status `analyzing` → `failed`, new starts unblocked.

Defects found and fixed by the live validation itself:

1. The pre-existing builder image tag `ghcr.io/astral-sh/uv:0.11.33-python3.12`
   does not exist on GHCR (no version-prefixed tags are published) — the old
   Dockerfile was never buildable. uv is now pip-pinned in the builder.
2. A dropped `WORKDIR` in the runtime stage mislocated `alembic.ini`
   (caught by the failing migrate service; fixed and re-verified).
3. Semgrep crashes as a non-root user when the home directory is missing
   (`~/.semgrep` user log) — `/home/app/.semgrep` is now pre-created.
4. Latent naive-datetime crash in `ScannerRunRepository` duration math on
   SQLite — found by the new reaper tests, fixed with the orchestrator's
   tolerant `_elapsed_ms` helper (also fixes cancel/timeout paths).

## Security notes

- Image still runs as the unprivileged `app` user; volume mount points are
  pre-created with its ownership so nothing runs as root.
- Pinned scanner versions (verified release URLs) — the March 2026 Trivy
  release incident makes pinning a supply-chain requirement, not a nicety.
- Compose requires an explicit 32+ byte `SESSION_JWT_SECRET` (fail-fast
  `:?` check) and sets `ENVIRONMENT=production` (HSTS, docs disabled).
- No new subprocess surface, no new endpoints, no schema changes.

## Known limitations

- Compose targets linux/amd64 scanner tarballs (the Go tools ship no
  linux/arm64 release assets for some pins); Apple Silicon hosts run the
  stack under emulation or on a linux/amd64 host.
- Recovery does not re-queue or notify; the UI shows the failed reason.
- The reaper assumes single-writer semantics at startup; multi-worker
  deployments must use the CLI path (documented in ADR 0017).
