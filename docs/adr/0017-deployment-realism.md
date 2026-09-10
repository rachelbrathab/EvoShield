# ADR 0017 — Deployment Realism: Scanner-Bundled Image and Stranded-Run Recovery

- **Status:** Accepted (Sprint 8)
- **Supersedes:** none
- **Related:** ADR 0008 (analysis domain), ADR 0009 (scanner architecture), ADR 0011 (multi-scanner orchestration)

## Context

Sprint 7 completed the functional pipeline (repository acquisition → four
scanners → normalized findings → intelligence → remediation). Two
deployment-facing defects remained, plus accumulated dead scope:

1. **The backend image could not scan.** `apps/backend/Dockerfile` installed
   the Python environment only — no Trivy, Gitleaks, Semgrep, Syft or Grype
   binaries, and not even `git` for repository acquisition. The declared
   core capability existed only on developer machines.
2. **A restart stranded active runs forever.** Runs execute as in-process
   `asyncio` tasks (ADR 0008 deliberately keeps the execution mechanism
   swappable). When the process dies, the run rows stay `queued`/`running`,
   the repository stays `analyzing`, and the DB-level
   `uq_analysis_runs_active_repository` guard (migration 0005) rejects every
   future start for that repository. Recovery required hand-editing the DB.
3. **Cancelled scope still haunted the tree.** Empty `prediction`, `chat`,
   `recommendation` and `reports` domain stubs and frontend "Coming soon"
   cards (one linking to a non-existent route) misrepresented the product.

## Decision

### 1. Ship the scanner toolchain inside the backend image

Scanner binaries are pinned (`ARG TRIVY_VERSION=0.74.0`,
`GITLEAKS_VERSION=8.30.1`, `SYFT_VERSION=1.51.1`, `GRYPE_VERSION=0.118.0`,
`SEMGREP_VERSION=1.176.1`), downloaded from their official release
artifacts, and **verified at build time** (`--version` for every tool — a
broken layer fails the build instead of every future scan). Semgrep is a
Python application and installs into an isolated venv to avoid clashing
with EvoShield's locked dependency set. `git` is installed for acquisition.
Alternatives rejected:

- *Install at container start* — non-reproducible, network-dependent at
  boot, impossible to verify what actually runs.
- *Sidecar scanner container* — violates the in-process provider
  architecture (ADR 0009/0011) and adds orchestration complexity the
  project explicitly avoided.

Pinning is also a supply-chain control: the March 2026 Trivy release
compromise demonstrated that floating tags on scanner tooling are an attack
surface. Bumps are deliberate: verify the asset URL, re-run a real scan.

### 2. Recover stranded runs at startup, expose recovery as a CLI

`recover_stranded_runs()` (in the `analysis` domain, not a new one)
transitions every active run to FAILED with an explanatory
`failure_reason`, fails its PENDING/RUNNING scanner runs, and resets
repositories stuck in `queued`/`analyzing` to `failed`. It runs:

- in the FastAPI **lifespan** hook (default, `REAPER_ENABLED=true`) for the
  single-process deployment this project targets; and
- as `python -m app.cli recover-runs` from the compose `migrate` job for
  multi-worker deployments, where per-worker startup recovery would race.

Design constraints honored:

- **No terminal state is ever rewritten** — only queued/running rows match.
- **No auto-re-queueing** — scans require fresh clone acquisition and
  operator intent; recovered runs are simply re-startable from the UI/API.
- **No new schema** — recovery reuses existing states and columns; the
  explanatory reason lives in the existing `failure_reason` (512 chars).
- **Recovery failure never blocks serving** — the lifespan hook catches and
  logs; the API still boots.

### 3. Containerize the frontend and compose the full stack

Next.js already built with `output: "standalone"`, so the runtime image is
the standard minimal standalone pattern (non-root, healthcheck, build-arg
`NEXT_PUBLIC_API_URL` because `NEXT_PUBLIC_*` is inlined at build time).
`docker-compose.yml` models the production shape: healthcheck-gated
Postgres, a one-off migrate service (`alembic upgrade head` +
`recover-runs`), the scanner-bundled backend with named volumes for the
Trivy/Grype advisory caches and the clone workspace, and the frontend. The
compose file fails fast when `SESSION_JWT_SECRET` is unset.

### 4. Delete dead scope, do not promise it

The empty domain stubs and placeholder nav/cards are removed. The roadmap in
the README now reflects only what exists or is genuinely planned.

## Consequences

- A fresh `docker compose up --build` yields a fully working EvoShield that
  performs real four-scanner analyses — the demo/defence path no longer
  depends on a developer's laptop state.
- Scanner version bumps are one `ARG` each, with build-time verification.
- Restart resilience: repositories can never be permanently deadlocked by a
  crash; the failure reason is visible in the run history UI.
- Known trade-offs: images grew by the scanner toolchain (~hundreds of MB);
  Go scanner pins target linux/amd64 release assets (arm64 hosts run under
  emulation); the reaper assumes single-writer semantics unless the CLI
  path is used.

## Compliance

- No `shell=True`, no new subprocess call sites, no scanner-output exposure
  changes; acquisition/subprocess guarantees from ADR 0010/0012/0013/0014
  are untouched.
- Owner scoping unaffected (recovery is a global startup maintenance task,
  not an API surface; run ids are logged only, never exposed).
- No database schema changes; all 8 migrations remain the source of truth.
