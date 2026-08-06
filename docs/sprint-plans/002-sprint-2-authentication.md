# Sprint 2 — Authentication

> **Status:** ✅ Shipped — 2026-08-03

## Goal

A production-ready authentication system for EvoShield: register, login, logout,
GitHub OAuth, JWT sessions, protected routes and user-profile provisioning —
built on the domain-oriented clean architecture from the Sprint 1 review so the
identity code never leaks into other domains.

## Design decisions

1. **Provider behind a port.** The `identity` domain defines an `AuthProvider`
   port. Two implementations exist: a **local provider** (password hashing +
   HS256 JWTs, zero external dependencies — the dev/test default) and a
   **Supabase provider** (server-side password auth + JWT verification with
   `SUPABASE_JWT_SECRET`). `AUTH_PROVIDER=auto` picks Supabase when
   credentials are configured, otherwise falls back to local — mirroring the
   SQLite/Postgres database fallback from ADR 0001. See
   `docs/adr/0005-identity-auth.md`.
2. **httpOnly session cookie.** The access token lives in an httpOnly, SameSite
   Lax cookie (`evoshield_session`) so browser clients are protected from XSS
   token theft; the token is also returned in the body for API clients using
   the Authorization header. Both are accepted by `get_current_user`.
3. **GitHub OAuth with CSRF-safe state.** `/auth/oauth/github` redirects to
   GitHub with a random state stored in an httpOnly cookie; the callback
   verifies the echoed state before exchanging the code — preventing login
   CSRF. New GitHub users get a deterministic UUID profile
   (`identifiers.py` handles GitHub's numeric IDs).
4. **Separation of concerns.** The identity domain owns models, schemas, ports,
   providers, JWT/password utilities and the service. Routers only wire HTTP.
   No identity code touched the frontend's domain logic; the frontend consumes
   the API via `lib/api.ts` and holds session state in `lib/auth.tsx`.

## Features

- Register (email + password + optional name) → auto-login → session cookie
- Login → session cookie; logout → token revocation (local provider) + cookie clear
- `/auth/me` and `/auth/session/check` protected endpoints
- GitHub OAuth start + callback (state-verified) with profile provisioning
- Password hashing (argon2 via `pwdlib`), timing-safe verification
- JWT minting/verification with expiry, provider claim, issuer validation
- Protected frontend routes via `src/proxy.ts` (Next 16) + client-side guard
- Session-aware API client, `AuthProvider` context, user menu with sign-out

## Folder structure (new)

```
apps/backend/app/
├── domains/identity/           NEW identity domain
│   ├── __init__.py             dependency-rule docstring
│   ├── ports.py                AuthProvider port + AuthUser/AuthResult DTOs
│   ├── jwt.py                  HS256 mint + verify (exp, iss, provider claim)
│   ├── passwords.py            argon2 hash + verify (pwdlib)
│   ├── identifiers.py          deterministic UUIDs from external IDs
│   ├── schemas.py              Register/Login/UserProfile/AuthResponse DTOs
│   ├── repository.py           user profile persistence (upsert + load)
│   ├── local_provider.py       password + JWT provider (dev/test default)
│   ├── supabase_provider.py    Supabase REST auth + JWT verification
│   ├── github_oauth.py         OAuth URL builder + code exchange (httpx)
│   ├── service.py              IdentityService: register/login/logout/authenticate
│   └── factory.py              cached provider selection (auto/supabase/local)
├── models/
│   ├── user.py                 extended: password_hash, auth_provider, last_login_at
│   └── credential.py           NEW revoked-JWT registry (local provider)
└── api/
    ├── deps.py                 get_current_user (bearer | cookie), get_identity_service
    └── routers/auth.py         register/login/logout/me/oauth/session-check

apps/backend/alembic/versions/20260803_0002_auth_identity.py   migration 0002

apps/frontend/src/
├── middleware.ts  →  src/proxy.ts   Next 16 renamed convention, session guard
├── lib/
│   ├── api.ts                      auth API methods (register/login/logout/me)
│   └── auth.tsx                    AuthProvider + useAuth (session state, signOut)
├── app/
│   ├── layout.tsx                  AuthProvider now wraps the whole app
│   ├── login/page.tsx              login form + GitHub OAuth + error states
│   ├── register/page.tsx           registration form
│   └── app/
│       ├── layout.tsx              protected app shell (sidebar, user menu)
│       └── page.tsx                dashboard with account status
└── components/
    ├── auth/auth-card.tsx          shared auth page chrome
    └── site/ (header, cta-section) CTAs now point at real auth routes
```

## Database changes

Migration `0002` (dialect-safe for Postgres + SQLite):

- `users`: add `password_hash` (nullable — OAuth users), `auth_provider`
  (`local` | `supabase` | `github`, default `local`), `last_login_at`.
- New `credentials` table: `id` UUID pk, `user_id` FK → users, `token_jti`
  unique, `revoked_at` — the local provider's revocation registry
  (logout invalidates the JWT server-side).

## API endpoints (v1)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/register` | — | Create account, set session cookie |
| POST | `/auth/login` | — | Verify credentials, set session cookie |
| POST | `/auth/logout` | — | Revoke token (local), clear cookie |
| GET | `/auth/me` | ✅ | Current user profile |
| GET | `/auth/session/check` | ✅ | Session validation for the frontend |
| GET | `/auth/oauth/github` | — | Start GitHub OAuth (307 → github.com) |
| GET | `/auth/oauth/github/callback` | — | Exchange code, verify state, set cookie, → `/app` |
| GET | `/health` | — | Liveness (unchanged) |

See `docs/api.md` for full request/response contracts.

## Frontend pages

- `/login` — email/password, GitHub OAuth button, error toast, `next` redirect
- `/register` — name/email/password with inline validation
- `/app` (protected) — dashboard with account status + session-aware shell
- `/app/*` — future pages behind the same shell

## Acceptance criteria

- [x] Register creates a user, sets an httpOnly session cookie, redirects to `/app`
- [x] Login verifies argon2-hashed passwords; wrong password → 401, no leak
- [x] Logout revokes the token (local provider) and clears the cookie
- [x] Protected endpoints reject missing/invalid/expired tokens (401)
- [x] GitHub OAuth flow implemented with state-CSRF protection
- [x] Migration 0002 applies cleanly on fresh SQLite and the dev DB
- [x] Backend: `ruff check`, `ruff format --check`, `pyright` (0 errors), `pytest` — 36 passed
- [x] Frontend: `eslint`, `tsc --noEmit`, `next build` all pass
- [x] Live UI verified: register → dashboard, sign out → login, sign in → dashboard

## Testing strategy

- **Unit** (`tests/unit/domains/identity/`): JWT mint/verify/expiry/issuer,
  password hash round-trip + wrong-password rejection, identifier
  determinism (GitHub numeric IDs).
- **Integration** (`tests/integration/test_auth.py`): full register →
  `/me` → logout → 401 flow over the real FastAPI stack + SQLite; cookie-jar
  persistence; per-test DB reset for isolation.
- **Manual/live**: dev servers + real browser session flow (register, logout,
  login) against the running stack.

## Out of scope (next sprints)

- GitHub repository integration (Sprint 3 — uses the identity user/session).
- Email verification, password reset flows (Sprint 2 hardening candidates).
- Multi-tenancy and roles (beyond the single `user` role today).
