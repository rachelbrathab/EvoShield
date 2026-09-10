# Domain Overview

Each folder under `app/domains/` is a self-contained business domain. This
document describes what each owns, what it consumes, and when it ships.

## Principles

- **One domain, one responsibility.** No domain imports another.
- **Ports before tools.** Domains depend on ports (interfaces) defined by the
  domain; concrete implementations (scanner binaries, GitHub API, LLM vendor)
  are injected — so swapping a tool never rewrites a domain.
- **Orchestration outside domains.** Cross-domain flows live in `workers/` and
  the API layer.

## Domain table

| Domain | Ships (Sprint) | Owns | Consumes | Produces |
| --- | --- | --- | --- | --- |
| `identity` | 2 ✅ | Register/login/logout, JWT sessions, GitHub OAuth, user profiles | Supabase Auth / local provider (behind port) | Authenticated user + session |
| `health` | 1 ✅ | Liveness + dependency probes | Database | Health payload |
| `github` | 3A ✅ | GitHub OAuth (via identity), REST API client, repository import/sync/query, GitHub repo browser, repository contract (`RepositoryRead`) | GitHub API (external, behind `GitHubRepoProvider` port) | Normalized repository data |
| `analysis` | 4A ✅ | Run lifecycle orchestration — `AnalysisRun` history, `AnalysisProvider` port, state machine, timeout/cancellation | Repository rows + injected provider (behind port) | Completed/failed run records; repository `analysis_status` transitions |
| `scanners` | 5–5C.4 ✅ | Trivy/Syft/Grype/Semgrep/Gitleaks execution, finding normalization | Analysis artifacts | Unified `Finding` model |
| `intelligence` | 6 ✅ | Deterministic risk scoring, aggregation, prioritization, trend, scanner coverage | Findings + scanner runs | Repository intelligence payload |
| `remediation` | 7 ✅ | Finding status lifecycle, deterministic guidance, fix availability, remediation priority | Findings + user status updates | Remediation intelligence payload |
| `analysis` reaper | 8 ✅ | Stranded-run recovery at startup (`reaper.py`, `app/cli.py`) | Active analysis runs | Failed runs with explanatory reason |

## Data flow (pipeline)

```
GitHub ──▶ Analysis ──▶ Scanners ──▶ Intelligence ──▶ Remediation ──▶ Security posture
```

## Per-domain detail

### health (reference implementation)
The smallest complete domain and the pattern every other domain follows:
`service.py` (logic) + `schemas.py` (contract) + a router adapter. The
database probe accepts an injectable engine, which is why it has real unit
tests (`tests/unit/domains/health/`).

### identity (Sprint 2)
Authentication is its own bounded context: an `AuthProvider` port with two
adapters (local argon2+JWT for dev/test, Supabase for production) and GitHub
OAuth. Because the domain depends on a port, switching or adding identity
backends never rewrites other domains (ADR 0005).

### analysis (Sprint 4A ✅)
The orchestration layer every future scanner plugs into. `AnalysisRun`
records one pipeline execution (`queued · running · completed · failed ·
cancelled`) with timing and outcome; the orchestrator mirrors the run state
onto the repository's `analysis_status` (queued → analyzing → analyzed /
failed / not_analyzed) and stamps `last_analysis_at` + `last_analysis_job_id`.
Scanners implement the `AnalysisProvider` port (`name`, `version`,
`supports`, `execute`) and are selected via `factory.py` — the fake provider
is the Sprint 4A default and simulates runs (configurable delay, failure
mode, cooperative cancellation). Owner scoping derives through the
repository row; the API exposes start/list/detail/cancel/delete for runs
only. See `docs/adr/0008-analysis-domain.md`.

### github (Sprint 3A ✅)
The source-provider domain. `ports.py` defines the `GitHubRepoProvider`
interface; `github_client.py` is the GitHub REST adapter; `service.py` owns
the business rules — **idempotent import** (upsert on the `(owner_id,
full_name)` natural key, 201 new / 200 re-import), **in-place sync**
(refreshes metadata and stamps `last_synced_at`; a repository deleted
upstream is kept but marked `is_active=false` with a warning), and
**owner-scoped queries** (another user's repository returns 404).
GitLab, Bitbucket and Azure DevOps are added as sibling adapters
implementing the same port — no downstream changes (see
`docs/module-dependency.md`). The identity domain persists the user's
GitHub access token in `provider_tokens` during OAuth (ADR 0007); the
service reads it through shared data access.

### provider_tokens (Sprint 3A)
Per-user upstream access tokens (`UNIQUE (user_id, provider)`). Written by
the identity domain's GitHub OAuth callback, read by the github domain so
the API can call GitHub as the user without re-authenticating. Plain text
in dev; production must encrypt at rest (Sprint 12). See
`docs/adr/0007-github-integration.md`.

### Analysis status (Sprint 3 preparation)
Every repository carries one *current* analysis lifecycle state
(`not_analyzed · queued · analyzing · analyzed · failed · cancelled`) — an
enum-backed VARCHAR on the `repositories` table (see `docs/adr/0006-analysis-status.md`).
It ships **before** any scanner so Sprint 3 ingestion and Sprint 4/5
pipelines both integrate against a stable, already-migrated schema. The
`RepositoryRead` contract exposes the status, and the frontend
`AnalysisStatusBadge` renders it — repository cards and detail pages drop it
in with zero redesign. Scan-specific data stays off the repository row:
scanners report progress by flipping `analysis_status` and write findings to
their own tables (Sprint 5).

### scanners (Sprint 5)
Scanner binaries are external infrastructure. The domain defines a
`Scanner` port; each tool (Trivy, Syft, …) is an adapter. Findings are
normalized into one `Finding` schema so downstream domains are tool-agnostic.

### analysis reaper (Sprint 8 ✅)
Analysis runs execute in in-process asyncio tasks, so a server restart
orphans any run whose task died. `reaper.py` closes that hole: every
queued/running run is transitioned to FAILED with an explanatory reason at
startup (lifespan hook) or via `python -m app.cli recover-runs` (one-off
container command for multi-worker deployments). Terminal runs are never
touched, and recovery is deliberately not auto-re-queueing — scans need
fresh acquisition and operator intent. See `docs/adr/0017-deployment-realism.md`.
