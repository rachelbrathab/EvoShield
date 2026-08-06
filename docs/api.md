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

## Notes

- `register`, `login` and the OAuth callback all end with a session cookie,
  so the frontend can go straight from form to the protected dashboard.
- The local provider is the dev default (`AUTH_PROVIDER=auto` picks Supabase
  when credentials are configured). See `docs/adr/0005-identity-auth.md`.
