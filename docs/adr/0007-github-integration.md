# ADR 0007 — Repository integration: GitHub OAuth tokens & import/sync semantics

- **Status:** Accepted
- **Date:** 2026-08-06
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 3A — repository integration platform

## Context

Sprint 3A must let a user connect GitHub, browse their repositories, import
them into EvoShield, sync metadata, and view details. Two questions drove the
design:

1. **How does the backend call the GitHub API as the user?** The Sprint 2
   GitHub OAuth flow exchanged a code for an access token, fetched the
   profile, and *discarded the token*. Import/sync need it again — with no
   re-authentication prompt.
2. **What are the import/sync semantics?** The `repositories` table (Sprint 3
   preparation) already existed with the analysis-status lifecycle; this ADR
   fixes how ingestion writes to it.

## Decisions

### 1. OAuth scope gains `repo`, and the token is persisted per user

- The OAuth scope is now `read:user user:email repo` — `repo` is required to
  list and import private repositories (the primary use case of a
  DevSecOps platform).
- The identity service's `github_callback` stores the access token in a new
  normalized `provider_tokens` table: `UNIQUE (user_id, provider)`.
- **Why a table and not a `users` column?** The (user, provider) shape scales
  to GitLab/Bitbucket/Azure DevOps tokens without altering `users`; it mirrors
  the `auth_credentials` precedent. One token per provider per user.
- **Security note:** tokens are stored as plain text in dev. Production
  deployments must encrypt at rest (Supabase column encryption or a
  KMS-backed envelope) — tracked in the Sprint 12 hardening milestone.
- The github domain reads tokens through shared data access
  (`app/repositories/provider_token.py`), never re-exchanges the code.

### 2. The `github` domain becomes the source-provider domain

The existing `domains/github/` (home of `RepositoryRead`) grows the full
integration layer, keeping all GitHub-specific code isolated:

```
domains/github/
├── ports.py           GitHubRepoProvider port + GitHubRepoData + factory
├── github_client.py   GitHub REST adapter (all GitHub-specific code)
├── service.py         RepositoryService (import/sync/query/delete/search)
├── repository.py      RepositoryRepository (data access, owner-scoped)
└── schemas.py         API contracts
```

GitLab/Bitbucket/Azure DevOps later ship as new adapters implementing
`GitHubRepoProvider` — no downstream domain changes (per the Sprint 3
planning docs).

### 3. Import is an idempotent upsert; sync refreshes in place

- `POST /repositories/import` fetches from GitHub and upserts on the
  `(owner_id, full_name)` natural key. First import → `201`; re-import →
  `200` with `was_already_imported: true` and refreshed metadata. Never
  duplicates.
- `PATCH /repositories/{id}/sync` refreshes metadata without re-importing
  and stamps `last_synced_at`. A repository deleted upstream is *kept* and
  marked `is_active = false` with a `warning` — history is not orphaned.
- `DELETE /repositories/{id}` untracks the EvoShield row (the upstream repo
  is untouched).
- Every query is scoped to the authenticated user (`owner_id`); cross-user
  access returns 404.

### 4. The `repositories` table is extended with metadata only

Migration 0004 adds provider metadata columns (language, stars, forks,
open_issues, topics, license, size, archived, disabled, upstream timestamps,
`last_synced_at`) — all nullable/defaulted, backward compatible. **No scan
data**: Sprint 5 scanners flip `analysis_status` and write findings to their
own tables (ADR 0006).

## Known limitations (deferred deliberately)

- **Renamed upstream repos**: sync fetches by the stored `full_name`; a
  rename upstream returns 404 and the repo is marked inactive (the UI says
  it no longer exists). Handling renames needs a lookup by
  `provider_repo_id` — a small port addition deferred to Sprint 3B.
- **Browse pagination**: the import dialog fetches one page (50) of the
  user's GitHub repositories with no “load more”; users with more repos use
  the import-by-name tab. The `has_more` flag is contract-level and unused
  by the UI today.

## Consequences

- Users see a "Connect GitHub" gate (401 `github_not_connected`) until they
  complete OAuth — the import dialog surfaces the connect action.
- The OAuth scope is broader than before; the UI documents why the `repo`
  scope is requested.
- `RepositoryRead` grows ~11 optional fields; existing clients and the
  Sprint 3-preparation tests remain valid.
- Providers beyond GitHub need: an adapter + their own OAuth token storage
  (the `provider_tokens` table is ready), nothing else.
