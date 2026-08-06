# EvoShield API Reference

> The authoritative contract is the FastAPI OpenAPI schema at
> `/openapi.json` (see `docs/adr/0004-api-contract.md`). This document is the
> human-readable reference for the v1 surface, current as of Sprint 2.

Base URL: `http://localhost:8000` (dev) — `/api/v1` prefix on all endpoints.

## Conventions

- **Errors** return `{"detail": "..."}` with a proper status code (400
  validation, 401 unauthenticated, 403 forbidden, 404 not found, 409
  conflict, 500 internal).
- **Sessions:** browser clients get an httpOnly `evoshield_session` cookie.
  API clients may instead send `Authorization: Bearer <token>`.
- **JSON** everywhere; CORS allowlist for the frontend origin.

## Health

### GET `/api/v1/health`

Liveness + dependency probe. No auth.

```json
{ "status": "ok", "version": "0.1.0", "environment": "development",
  "database": "ok", "timestamp": "2026-08-03T12:00:00Z" }
```

## Auth

### POST `/api/v1/auth/register`

Create an account. Sets the session cookie on success (auto-login).

```json
// request
{ "email": "ada@example.com", "password": "s3cret!", "full_name": "Ada Lovelace" }
// 201 response
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 43200,
  "user": { "id": "…uuid…", "email": "ada@example.com", "full_name": "Ada Lovelace",
            "avatar_url": null, "auth_provider": "local", "created_at": "…" } }
```

- `409` — email already registered.

### POST `/api/v1/auth/login`

```json
// request
{ "email": "ada@example.com", "password": "s3cret!" }
// 200 response — same shape as register
```

- `401` — invalid credentials (no user-enumeration hint).

### POST `/api/v1/auth/logout`

Clears the session cookie; revokes the token server-side (local provider).

```json
// 200 response
{ "message": "Logged out" }
```

### GET `/api/v1/auth/me`

Auth required (cookie or bearer). Returns the current profile:

```json
{ "id": "…uuid…", "email": "ada@example.com", "full_name": "Ada Lovelace",
  "avatar_url": null, "auth_provider": "local", "created_at": "…" }
```

### GET `/api/v1/auth/session/check`

Auth required. Same payload as `/me` — used by the frontend session guard
(`401` → redirect to login).

### GET `/api/v1/auth/oauth/github`

No auth. Issues an httpOnly `evoshield_oauth_state` cookie and
`307`-redirects to GitHub's authorization page.

### GET `/api/v1/auth/oauth/github/callback?code=…&state=…`

- Verifies `state` against the `evoshield_oauth_state` cookie (CSRF), then
  exchanges `code` for a session.
- On success: `307` → `{frontend_url}/app` with the session cookie set.
- `403` — state mismatch.
- Sprint 3A: the callback also persists the GitHub access token
  (`provider_tokens` table) so the repository integration layer can call
  the GitHub API as the user. OAuth scope: `read:user user:email repo`.

## Repositories

Auth required on every endpoint (cookie or bearer). All queries are scoped
**to the authenticated user** — another user's repositories return `404`.
GitHub errors map to the shared error contract (`401` token invalid,
`429` rate limit, `404` missing/deleted, `502` GitHub unavailable).

### GET `/api/v1/repositories`

List tracked repositories with pagination, filtering and sorting.

Query params:

| Param | Description |
| --- | --- |
| `page` | 1-based page (default 1) |
| `page_size` | Rows per page, 1–100 (default 20) |
| `q` | Search name / owner / description (ILIKE) |
| `language` | Exact language filter, e.g. `Python` |
| `visibility` | `public` \| `private` |
| `analysis_status` | `not_analyzed` \| `queued` \| `analyzing` \| `analyzed` \| `failed` \| `cancelled` |
| `archived` | `true` \| `false` — filter by GitHub archived state (Sprint 3B) |
| `disabled` | `true` \| `false` — filter by GitHub disabled state (Sprint 3B) |
| `imported_after` | ISO timestamp — only repos tracked after this time (Sprint 3B) |
| `sort` | `name` \| `stars` \| `forks` \| `language` \| `size_kb` \| `pushed_at` \| `created_at` \| `updated_at` (default `updated_at`) |
| `order` | `asc` \| `desc` (default `desc`) |

Sprint 3B added `archived`, `disabled`, `imported_after` and the
`forks`/`language`/`size_kb` sort keys; all additions are backward compatible
(absent params behave exactly as before).

```json
{ "items": [ { "id": "…uuid…", "full_name": "octocat/Hello-World",
    "language": "Python", "stars": 42, "forks": 7, "open_issues": 3,
    "topics": ["demo"], "license": "MIT", "size_kb": 185,
    "pushed_at": "…", "last_synced_at": "…",
    "analysis_status": "not_analyzed", "is_private": false, "is_active": true, "…": "…" } ],
  "page": 1, "page_size": 20, "total": 1, "total_pages": 1 }
```

### GET `/api/v1/repositories/search`

Browse the user's GitHub repositories for the import dialog.

Query params: `q` (filter name/description), `page`, `per_page` (1–100).
Returns `{ items: GitHubRepositoryCandidate[], page, has_more }`.

- `401` `github_not_connected` — the user has not connected GitHub yet.

### GET `/api/v1/repositories/{id}`

Detail for one tracked repository. `404` if not found or not owned.

### POST `/api/v1/repositories/import`

```json
// request
{ "full_name": "octocat/Hello-World" }
// 201 (new) / 200 (already tracked) — idempotent
{ "repository": { "…" }, "was_already_imported": false }
```

- `422` — `full_name` is not in `owner/name` form.
- `404` — repository does not exist on GitHub.
- `401` `github_not_connected` — no GitHub account connected.

### PATCH `/api/v1/repositories/{id}/sync`

Refresh metadata from GitHub without re-importing.

```json
{ "repository": { "…" }, "warning": null }
// deleted upstream → 200 with is_active:false and a warning
```

### DELETE `/api/v1/repositories/{id}`

Untrack the repository. `204` on success; the GitHub repo is untouched.

## Analysis (Sprint 4A)

Auth required on every endpoint (cookie or bearer). Runs are scoped **to the
authenticated user** through the repository row (`run → repository → owner`)
— another user's run (or a run on another user's repository) returns `404`.

All endpoints operate on `AnalysisRun` records only. No scanner executes:
the orchestrator dispatches the configured provider (the fake simulation
today; Trivy/Syft/Grype/Semgrep/Gitleaks from Sprint 5) in the background.

Run status vocabulary: `queued · running · completed · failed · cancelled`.
A repository can have at most one active (queued/running) run.

### POST `/api/v1/repositories/{id}/analysis`

Queue a new analysis run for a repository. `201` on success. The run starts
as `queued` and dispatches asynchronously.

```json
{ "run": { "id": "…uuid…", "repository_id": "…uuid…",
  "repository_full_name": "octocat/Hello-World", "triggered_by": "user",
  "status": "queued", "started_at": null, "completed_at": null,
  "duration_ms": null, "analysis_version": "0.1.0",
  "failure_reason": null, "created_at": "…", "updated_at": "…" } }
```

- `404` — repository not found or not owned.
- `409` — repository already has an active (queued/running) run.

### GET `/api/v1/analysis`

List the user's analysis runs, newest first, with pagination.

Query params: `page` (default 1), `page_size` (1–100, default 20),
`repository_id` (filter to one repository), `status`
(`queued|running|completed|failed|cancelled`).

```json
{ "items": [ { "run": { "…" } } ], "page": 1, "page_size": 20, "total": 1, "total_pages": 1 }
```

### GET `/api/v1/repositories/{id}/analysis`

List runs for one repository (same pagination/filter shape as above).
`404` if the repository is not found or not owned.

### GET `/api/v1/analysis/{id}`

Detail for one run (same shape as the create response, minus the wrapper).
`404` if not found or not owned. The frontend polls this while a run is
active to render the live timeline.

### POST `/api/v1/analysis/{id}/cancel`

Cancel a `queued` or `running` run (cooperative cancellation — the provider
polls a per-run event). `200` with the updated run.

- `404` — run not found or not owned.
- `409` — run is already in a terminal state (`completed`/`failed`/`cancelled`).

### DELETE `/api/v1/analysis/{id}`

Delete a **terminal** run record. `204` on success.

- `404` — run not found or not owned.
- `409` — run is still active (queued/running).

## Notes

- `register`, `login` and the OAuth callback all end with a session cookie,
  so the frontend can go straight from form to the protected dashboard.
- The local provider is the dev default (`AUTH_PROVIDER=auto` picks Supabase
  when credentials are configured). See `docs/adr/0005-identity-auth.md`.
