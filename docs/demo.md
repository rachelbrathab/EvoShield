# EvoShield — End-to-End Demonstration Guide

This guide demonstrates the complete EvoShield workflow on a real deployment
(Docker Compose, PostgreSQL, real scanners). Every command and endpoint below
is taken from the current codebase.

**What EvoShield does:** connects GitHub repositories, acquires them securely,
runs four scanner pipelines (Trivy vulnerability/secret/config scanning,
Gitleaks secret detection, Semgrep SAST, Syft→Grype SBOM + vulnerability
matching), normalizes their output into a unified finding model, and computes
deterministic risk intelligence, prioritization and remediation guidance over
those findings — all owner-scoped behind authentication.

---

## 1. Prerequisites

- Docker Engine 24+ with Compose v2 (`docker compose version`)
- ~4 GB free RAM (scanner advisory DBs are cached in volumes)
- Internet access (first run pulls images + scanner vulnerability databases)
- For the repository-import step: a GitHub account, and a GitHub OAuth App
  (Settings → Developer settings → OAuth Apps) with callback URL
  `http://localhost:8000/api/v1/auth/oauth/github/callback`

## 2. Environment configuration

```bash
cp .env.compose.example .env.compose
```

Edit `.env.compose`:

| Variable | Required | Notes |
| --- | --- | --- |
| `SESSION_JWT_SECRET` | yes | 32+ bytes, e.g. `openssl rand -hex 32` |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | for repo import | from your OAuth App |
| `GITHUB_REDIRECT_URI` | for repo import | `http://localhost:8000/api/v1/auth/oauth/github/callback` |
| `BACKEND_PORT` / `FRONTEND_PORT` | no | defaults 8000 / 3000 |

PostgreSQL credentials have working defaults (`evoshield`/`evoshield`) — the
database is only reachable inside the compose network.

## 3. Start the stack

```bash
docker compose --env-file .env.compose up --build -d
```

Compose starts, in dependency order:

1. `db` — PostgreSQL 16 (healthcheck-gated)
2. `migrate` — one-off container: `alembic upgrade head` (0001→0008) plus
   stranded-run recovery, then exits 0
3. `backend` — FastAPI + the full scanner toolchain (Trivy, Gitleaks, Semgrep,
   Syft, Grype, git), non-root, on `:8000`
4. `frontend` — Next.js standalone build, non-root, on `:3000`

Verify:

```bash
curl -s http://localhost:8000/api/v1/health
# {"status":"ok","version":"0.1.0","environment":"production","database":"ok",...}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
# 200
```

## 4. Create a user

Open **http://localhost:3000/register** and register, or via API:

```bash
curl -s -c /tmp/evoshield-cookies.txt -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"demo-password-123","full_name":"Demo User"}'
```

## 5. Connect GitHub and add a repository

1. Log in at **http://localhost:3000/login** (or use GitHub OAuth).
2. Use **Connect GitHub** to authorize the OAuth App — this persists the
   access token server-side (`provider_tokens`), never in the browser.
3. On the dashboard, **Import repository** and pick a small repository.
   Good demo candidates: a small Node.js project (a `package-lock.json`
   yields Syft/Grype dependency findings), or any repository with a secret
   in its git history (Gitleaks scans history).

Via API:

```bash
curl -s -b /tmp/evoshield-cookies.txt -X POST http://localhost:8000/api/v1/repositories/import \
  -H "Content-Type: application/json" -d '{"full_name":"owner/name"}'
```

## 6. Start an analysis

On the repository page, start an analysis (or via API):

```bash
curl -s -b /tmp/evoshield-cookies.txt -X POST \
  http://localhost:8000/api/v1/repositories/<REPO_ID>/analysis
```

The orchestrator acquires the repository into a temporary workspace (size
capped, cleaned up in a `finally`), then runs each configured scanner
sequentially (`ANALYSIS_SCANNERS=trivy,gitleaks,semgrep,grype`), recording a
`scanner_runs` row per scanner with isolated failure handling. Watch the live
status timeline on the analysis page (`GET /api/v1/analysis/<RUN_ID>`).

> First run downloads the Trivy and Grype advisory databases (~1–2 min);
> they are cached in the `scanner-cache` volume for subsequent runs.

## 7. Explore results

On the analysis page (all of it is backed by owner-scoped APIs):

| What | Where / API |
| --- | --- |
| Findings (severity, type, scanner, location) | Findings section · `GET /api/v1/analysis/<RUN_ID>/findings?severity=&finding_type=` |
| Risk score + level, aggregation, risk factors, top prioritized findings, trend vs previous run, scanner coverage | Intelligence section · `GET /api/v1/analysis/<RUN_ID>/intelligence` |
| Remediation metrics, per-finding guidance, fix availability, priority order | Remediation section · `GET /api/v1/analysis/<RUN_ID>/remediation` |

Acknowledge or resolve a finding from the remediation section (or via API):

```bash
curl -s -b /tmp/evoshield-cookies.txt -X PATCH \
  http://localhost:8000/api/v1/analysis/<RUN_ID>/findings/<FINDING_ID>/status \
  -H "Content-Type: application/json" \
  -d '{"status":"acknowledged","note":"Triaged in sprint review"}'
```

Lifecycle: `open → acknowledged → resolved | false_positive`.

Re-running the analysis after fixing issues produces a new run whose
intelligence trend compares against the previous completed run — that
delta is the security-posture improvement story.

## 8. Stop the stack

```bash
docker compose --env-file .env.compose down          # keep data
docker compose --env-file .env.compose down -v       # full reset (drops DB)
```

## 9. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Compose aborts: `SESSION_JWT_SECRET` required | Set a 32+ byte value in `.env.compose` |
| Port 8000/3000 already in use | Set `BACKEND_PORT` / `FRONTEND_PORT` |
| Import fails `401 github_not_connected` | Complete the GitHub OAuth connection first |
| OAuth callback mismatch | Callback URL must be exactly `http://localhost:8000/api/v1/auth/oauth/github/callback` |
| First scan slow | Advisory DB downloads; cached in `scanner-cache` volume afterwards |
| A scanner fails but the run continues | By design — scanner failures are isolated per `scanner_run`; the run completes with partial coverage shown in scanner coverage |
| Backend restarted mid-scan, run stuck `running` | Startup recovery marks it `failed` automatically (`python -m app.cli recover-runs` also works manually); restart the analysis |
| Check backend logs | `docker compose logs backend` |

---

## 5-minute demo flow (presentation script)

1. **(0:00)** `docker compose --env-file .env.compose up -d` — point out the
   one-command stack: PostgreSQL, migrations + recovery, scanner-bundled API.
2. **(1:00)** Open `http://localhost:3000`, register, connect GitHub.
3. **(1:30)** Import a small repository, hit **Start analysis**, show the
   live run timeline.
4. **(2:30)** Walk the analysis page: **Findings** → **Intelligence**
   (risk score, risk factors, prioritization) → **Remediation**
   (guidance, fix availability).
5. **(3:30)** Acknowledge one finding via the UI; explain the lifecycle.
6. **(4:00)** Show the API contract live:
   `curl http://localhost:8000/api/v1/health` and the OpenAPI schema at
   `http://localhost:8000/openapi.json` (the Swagger UI is dev-only —
   disabled in production by design).
7. **(4:30)** Restart the backend container
   (`docker compose restart backend`) and point out startup recovery in the
   logs — interrupted runs never wedge the system.
