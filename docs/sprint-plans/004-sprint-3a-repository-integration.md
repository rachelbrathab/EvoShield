# Sprint 3A — Repository Integration Platform

> **Status:** ✅ Shipped — 2026-08-06

## Goal

Make EvoShield usable: a user can **login → connect GitHub → browse their
repositories → import them → view details → refresh metadata**. Explicitly
**not** included: scanning (Trivy/Syft/Grype/Semgrep/Gitleaks), prediction,
AI assistant, reports, background workers, and repository cloning — those
belong to later sprints.

## Architecture decisions (see `docs/adr/0007-github-integration.md`)

1. **`domains/github/` is the source-provider domain.** It grows the full
   integration layer behind a `GitHubRepoProvider` port; `github_client.py`
   isolates every GitHub-specific detail (URLs, headers, payload mapping,
   rate-limit/error translation). GitLab/Bitbucket/Azure DevOps later ship as
   new adapters — no downstream changes.
2. **OAuth token persistence.** The GitHub OAuth scope gains `repo` (needed
   for private repos) and the callback persists the access token in a new
   normalized `provider_tokens` table (`UNIQUE (user_id, provider)`) so the
   API can act as the user without re-authenticating. Identity writes it,
   github reads it via shared data access.
3. **Import = idempotent upsert** on `(owner_id, full_name)`: 201 new / 200
   re-import with `was_already_imported`. **Sync refreshes in place** and
   stamps `last_synced_at`; a repo deleted upstream is kept but marked
   `is_active=false` with a warning. **Delete** untracks only the EvoShield
   row. Every query is owner-scoped (cross-user access → 404).
4. **Repository model extended with metadata only** (migration 0004: language,
   stars, forks, open_issues, topics, license, size, archived, disabled,
   upstream timestamps, `last_synced_at`) — no scan data.

## Files created / changed

```
apps/backend/app/
├── models/
│   ├── provider_token.py                 NEW ProviderToken model
│   └── repository.py                     + 11 GitHub metadata columns
├── repositories/provider_token.py        NEW shared token data access
├── domains/github/
│   ├── ports.py                          NEW source-provider port + GitHubRepoData
│   ├── github_client.py                  NEW GitHub REST adapter
│   ├── service.py                        NEW RepositoryService (import/sync/query/delete/browse)
│   ├── repository.py                     NEW owner-scoped RepositoryRepository
│   └── schemas.py                        RepositoryRead extended + list/import/sync/search contracts
├── api/
│   ├── routers/repositories.py           NEW 6-endpoint router
│   ├── router.py                         mount /repositories
│   └── deps.py                           get_repository_service DI
├── domains/identity/
│   ├── github_oauth.py                   OAuth scope += repo
│   └── service.py                        github_callback persists the token
└── core/config.py                        github_api_url setting
apps/backend/alembic/versions/20260806_0004_repository_integration.py   migration 0004
apps/backend/tests/
├── unit/domains/github/test_github_client.py            client normalization + error mapping (7)
├── unit/domains/github/test_repository_service.py       service rules with fakes (8)
├── unit/domains/identity/test_github_token_persistence.py  OAuth token persistence (2)
└── integration/test_repositories_api.py                 full HTTP→service→DB flow (13)
apps/frontend/src/
├── lib/repository.ts                 Repository type + metadata + list/import/search contracts
├── lib/repositories.ts               NEW API client for the repository endpoints
├── lib/api.ts                        export apiFetch (shared client)
├── lib/format.ts                     NEW relative time / compact numbers / size / language colors
├── components/ui/dialog.tsx          NEW Base UI Dialog wrapper
├── components/repositories/
│   ├── import-repository-dialog.tsx  NEW browse-GitHub + import-by-name dialog
│   ├── delete-repository-dialog.tsx  NEW confirm dialog
│   └── repository-card.tsx           NEW card (badges, stats, actions)
├── app/app/repositories/page.tsx     NEW list page (search/filters/sort/pagination/states)
├── app/app/repositories/[id]/page.tsx NEW detail page
└── app/app/layout.tsx · page.tsx     nav “Soon” removed for Repositories; dashboard live card
docs/
├── adr/0007-github-integration.md    NEW decision record
├── api.md · database.md · architecture.md · backend-structure.md · domain-overview.md · module-dependency.md  updated
└── sprint-plans/004-sprint-3a-repository-integration.md   this report
```

## Database changes (migration 0004, dialect-safe)

- **New `provider_tokens`**: per-user upstream access tokens,
  `UNIQUE (user_id, provider)`, FK → `users.id` CASCADE.
- **`repositories` +11 columns** (all nullable/defaulted): `language`,
  `stars`, `forks`, `open_issues`, `topics` (JSON), `license`, `size_kb`,
  `archived`, `disabled`, `provider_created_at`, `provider_updated_at`,
  `pushed_at` (indexed), `last_synced_at`.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /repositories` | List with pagination, search (`q`), filters (language/visibility/status), sort |
| `GET /repositories/search` | Browse the user's GitHub repos (import dialog) |
| `POST /repositories/import` | Idempotent import by `owner/name` |
| `GET /repositories/{id}` | Detail (404 if not owned) |
| `PATCH /repositories/{id}/sync` | Refresh metadata; deleted upstream → inactive + warning |
| `DELETE /repositories/{id}` | Untrack (204) |

Error handling: `401 github_not_connected` (no GitHub account), `401
github_token_invalid`, `429 github_rate_limited`, `404` missing/deleted,
`502` GitHub unavailable.

## Acceptance criteria

- [x] Login → connect GitHub → browse → import → detail → sync — the full
  flow works (verified live against the running API)
- [x] OAuth callback persists the access token in `provider_tokens`
- [x] Import idempotent (201 new / 200 re-import); never duplicates
- [x] Sync refreshes metadata; deleted-upstream repos marked inactive with a
  warning; history never orphaned
- [x] Delete untracks only the EvoShield row
- [x] Owner scoping enforced end-to-end (cross-user → 404)
- [x] GitHub API limits / missing / unauthorized / deleted / connection
  failures handled gracefully
- [x] No scanners, prediction, AI, reports, workers, or cloning added
- [x] Backend: `ruff check` + `format --check`, `pyright` (0 errors),
  `pytest` — **71 passed on SQLite and on PostgreSQL 16**
- [x] Frontend: `eslint`, `tsc --noEmit`, `next build` all pass
- [x] Migration 0004 applies cleanly on the dev DB and a fresh Postgres

## Implementation notes

- **Async-ORM pitfall fixed**: `updated_at` is server-computed
  (`onupdate=func.now()`), so it expires after commit and a Pydantic
  `model_validate` would trigger a lazy load outside the loop. The service
  explicitly refreshes rows after commit.
- **FK-ordering discipline**: the token-persistence test seeds a real `users`
  row — bare random ids violate Postgres FKs (SQLite doesn't enforce them).
- **Frontend effect rules**: eslint enforces `react-hooks/set-state-in-effect`
  (no synchronous setState in effects); data fetching uses the `.then` chain
  pattern already established by the auth module.

## How later sprints plug in

- **Sprint 4 (analysis)**: `analysis` domain adds `analysis_runs` history and
  transitions `Repository.analysis_status` — the columns already exist.
- **Sprint 5 (scanners)**: findings go to their own tables; only the status
  trio flips on the repository row (ADR 0006).
- **New providers**: GitLab/Bitbucket/Azure DevOps implement
  `GitHubRepoProvider` and store tokens in `provider_tokens`.
