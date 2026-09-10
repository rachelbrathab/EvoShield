# EvoShield — Final Completion Checklist

Objective criteria for declaring EvoShield complete. Every row lists the
evidence that was actually produced (Sprints 5A–9, final validation
September 2026). This checklist is the project's stopping rule: when every
box is checkable from the repository, EvoShield is complete — no further
feature sprints.

## 1. Core functionality

- [x] **Repository acquisition** — GitHub clone via credential helper
      (temp file, mode 0600), post-clone size cap, workspace cleanup in
      `finally` (`app/domains/scanners/providers/github_source.py`,
      ADR 0010)
- [x] **Analysis lifecycle** — `AnalysisRun` state machine
      (queued→running→terminal), DB-enforced single active run, cancel,
      delete (`app/domains/analysis/orchestrator.py`, ADR 0008)
- [x] **Multi-scanner orchestration** — sequential per-scanner runs,
      per-scanner `scanner_runs` rows, failure isolation
      (ADR 0011, migration 0007)
- [x] **Trivy** — provider/runner/parser; real execution verified in the
      shipped container (SchemaVersion 2 output on probe repo)
- [x] **Gitleaks** — provider/runner/parser; real execution verified
      (2 findings on a planted secret commit); exit-1-means-findings handled
- [x] **Semgrep** — provider/runner/parser with configurable ruleset;
      real execution verified (custom rule fired)
- [x] **Syft** — CycloneDX SBOM generation; real catalog verified
      (3 components from a lockfile)
- [x] **Grype** — Syft→Grype pipeline, transient SBOM deleted after use;
      real execution verified (5 matches with fix versions)
- [x] **Finding normalization** — one unified `Finding` model across four
      scanners (severity, type, scanner, location, fix availability)
- [x] **Finding storage** — owner-scoped chains
      (finding → analysis_run → repository → owner), migrations 0006–0008
- [x] **Intelligence** — deterministic aggregation (severity/type/scanner),
      risk factors with explanations, scanner coverage (ADR 0015)
- [x] **Risk scoring** — 0–100 deterministic score + level, unit-tested,
      no persistence of derived data
- [x] **Prioritization** — intelligence top-findings and remediation
      priority with explicit `priority_reason`
- [x] **Remediation guidance** — deterministic, explainable, per finding
      type incl. fix availability (ADR 0016)
- [x] **Finding status lifecycle** — `open → acknowledged → resolved |
      false_positive`, persisted in `finding_statuses` (migration 0008),
      owner-scoped PATCH endpoint
- [x] **Trend analysis** — latest run vs previous completed run of the same
      repository

## 2. Security

- [x] **Authentication** — local + Supabase providers, argon2, HS256 JWT in
      httpOnly SameSite cookie, bearer for API clients, GitHub OAuth with
      state-cookie CSRF protection (ADR 0005)
- [x] **Authorization / ownership** — every router scopes through owner
      chains; cross-user access returns 404 (tested)
- [x] **Secret redaction** — Gitleaks `Match` values never stored
      (test-enforced, `test_gitleaks_parser.py`)
- [x] **Source-code redaction** — Semgrep snippets/`metavars` never stored
      (test-enforced, `test_semgrep_parser.py`)
- [x] **Safe subprocess execution** — `asyncio.create_subprocess_exec` with
      argument arrays everywhere; no `shell=True`/`os.system` in `app/`
- [x] **Temporary-file cleanup** — workspaces and SBOMs cleaned on success,
      failure and timeout (verified: `/tmp/evoshield-scans` empty after runs)
- [x] **Path validation** — repository paths validated before scanner use;
      no user-controlled string concatenation into commands
- [x] **Non-root containers** — backend uid 999, frontend uid 1001
- [x] **Safe error handling** — scanner stderr never returned; exception
      taxonomy maps to safe HTTP messages; no stack traces to clients
- [x] **Secrets hygiene** — env-only configuration; no `.env` files in build
      contexts or git; `SESSION_JWT_SECRET` required at deploy time
- [x] **Scanner stderr / raw output** — never persisted to findings or API
      responses

## 3. Infrastructure

- [x] **PostgreSQL** — production target; migrations applied fresh
      0001→0008 on PostgreSQL 16 (Docker) and in CI; SQLite is local-dev
      fallback (ADR 0001, ADR 0017)
- [x] **Alembic** — head `20260821_48c42ca6936c_0008`; schema changes only
      via migrations
- [x] **Docker** — backend image bundles Trivy 0.74.0, Gitleaks 8.30.1,
      Semgrep 1.176.1, Syft 1.51.1, Grype 0.118.0, git; version pins
      verified against release assets; non-root; healthchecks
- [x] **Docker Compose** — one-command stack: db → migrate (+recovery) →
      backend → frontend, named volumes for pgdata and scanner caches
      (`docker-compose.yml`, `.env.compose.example`)
- [x] **Health checks** — `/api/v1/health` with DB probe; container
      HEALTHCHECKs on both images
- [x] **Recovery / reaper** — startup recovery marks restart-orphaned
      queued/running runs failed and unblocks repositories;
      `python -m app.cli recover-runs` CLI; live-verified against PostgreSQL

## 4. Testing

- [x] **Backend** — 442 pytest tests (unit + API-level), ruff + pyright clean
- [x] **Frontend** — 72 Vitest tests, ESLint + tsc clean, production build
- [x] **PostgreSQL** — full suite + migrations run on PostgreSQL 16 in CI
      (`backend-postgres` job)
- [x] **Docker** — images build in CI (`docker-images` job, Sprint 9) and
      locally; full stack smoke-tested (health, migrations, scanners,
      recovery)
- [x] **Real scanner execution** — all five binaries executed for real
      inside the production image during final validation (see
      `docs/sprint-plans/015-sprint-8-deployment-realism.md` and Sprint 9
      report)

## 5. Documentation

- [x] **README** — accurate product definition, quick start, Docker start,
      sprint roadmap through Sprint 9
- [x] **Architecture** — `docs/architecture.md` (layers, domains, security
      posture), `docs/backend-structure.md`, `docs/domain-overview.md`,
      `docs/module-dependency.md`
- [x] **API reference** — `docs/api.md` through Sprint 9 (findings,
      intelligence, remediation sections)
- [x] **Database** — `docs/database.md` + ADR 0001 + migrations as source of
      truth
- [x] **Demo guide** — `docs/demo.md` (prerequisites → teardown +
      5-minute presentation script)
- [x] **Sprint documentation** — 16 sprint plans/reports in
      `docs/sprint-plans/`
- [x] **ADRs** — 17 decision records (0001–0017)

## Verdict

All sections complete. **EvoShield is COMPLETE** as of Sprint 9.
Future work (explicitly out of scope, see `docs/sprint-plans/016-…md`):
CI/CD scanning integration, scheduled re-scans, report export, additional
VCS providers, out-of-process job execution.
