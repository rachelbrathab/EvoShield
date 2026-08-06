# ADR 0005 — Identity: provider behind a port, JWT sessions, httpOnly cookie

- **Status:** Accepted
- **Date:** 2026-08-03
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 2 authentication

## Context

EvoShield needs production-grade auth (register, login, logout, GitHub OAuth)
with Supabase Auth as the stated production backend — but local development and
the test suite must run with zero external credentials, exactly like the
SQLite fallback for Postgres (ADR 0001). We also need the frontend and backend
to stay cleanly separated: the frontend must never handle raw tokens in
JavaScript if we can avoid it.

## Decision

- **`identity` domain defines an `AuthProvider` port.** Two adapters:
  - **`local_provider`** — argon2 password hashing (pwdlib) + HS256 JWTs minted
    with a configurable secret; the zero-dependency dev/test default. Logout
    revokes tokens server-side via a `credentials` registry table.
  - **`supabase_provider`** — server-side REST auth (sign up / sign in with
    password) and JWT verification against `SUPABASE_JWT_SECRET`, so Supabase
    remains the production source of truth.
  - `AUTH_PROVIDER=auto` selects Supabase when credentials are configured and
    falls back to local — the same "prod when configured, frictionless
    otherwise" rule as the database layer.
- **JWT sessions.** Access tokens carry `sub`, `email`, `provider`, `iat`,
  `exp` (and `jti` for revocation). Verification enforces expiry, issuer and
  signature.
- **httpOnly session cookie.** `evoshield_session`, httpOnly + SameSite=Lax,
  `secure` behind TLS. The token is also returned in the response body for
  API clients using the Authorization header; `get_current_user` accepts
  either. Frontend JS never reads the raw token.
- **GitHub OAuth with CSRF-safe state.** The state value is stored in an
  httpOnly cookie and verified on callback before code exchange. GitHub
  numeric user IDs are mapped to deterministic UUIDs (`identifiers.py`) so
  `AuthUser.id` stays a UUID across providers.

## Consequences

- The whole stack (UI, tests, demo) runs without Supabase credentials.
- Swapping/adding providers (GitLab, Bitbucket later) is a new adapter behind
  the same port — no domain or API changes (Sprint 3 hooks in here).
- Two token paths (cookie + bearer) are both covered by `get_current_user` and
  by integration tests.
- The `credentials` revocation table is local-provider-only; Supabase revokes
  are delegated to Supabase (future hardening: validate `exp` is enough).

## Alternatives considered

- **Supabase only, no local provider:** rejected — CI and local dev would
  need live Supabase credentials; breaks the Sprint 1 "zero external services"
  rule.
- **Frontend-held tokens (localStorage):** rejected — XSS-exposed; httpOnly
  cookie is the standard mitigation and still works with the API.
- **OAuth implicit flow:** rejected — no PKCE/state handling; the
  authorization-code flow with server-side exchange is safer.
