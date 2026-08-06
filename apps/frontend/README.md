# EvoShield Frontend

Next.js 16 (App Router) application — the EvoShield SaaS UI.

## Stack

- Next.js 16 · React 19 · TypeScript (strict) · Tailwind CSS v4
- shadcn/ui (Base UI style) components in `src/components/ui/`
- `next-themes` for theming (dark-first tokens in `src/app/globals.css`)
- Live API status badge wired to the backend health endpoint

## Layout

```
src/
├── app/
│   ├── layout.tsx        root layout (AuthProvider, ThemeProvider, Toaster)
│   ├── page.tsx          landing page
│   ├── login/            login page (email/password + GitHub OAuth)
│   ├── register/         registration page
│   └── app/              protected workspace (shell + dashboard)
├── components/
│   ├── ui/               shadcn primitives (generated, don't hand-edit)
│   ├── auth/             shared auth-page chrome
│   └── site/             App-specific sections (header, hero, features, …)
├── lib/
│   ├── utils.ts          cn() helper
│   ├── api.ts            API client (health + auth contracts)
│   └── auth.tsx          AuthProvider + useAuth session context
└── proxy.ts              Next 16 edge guard for protected routes
```

## Authentication (Sprint 2)

- `AuthProvider` (in `lib/auth.tsx`) tracks the session: it calls
  `/auth/session/check` on mount, exposes `user` / `loading` / `signOut`.
- The protected `/app` shell redirects to `/login?next=…` when the session is
  missing; `proxy.ts` guards routes at the edge as a first line of defense.
- Login/register pages talk to the backend API; the session cookie is
  httpOnly, so client JS never sees the raw token.

## Run locally

```bash
npm install
npm run dev        # http://localhost:3000
```

The backend must be running on :8000 for the health badge and API calls
(see `apps/backend/README.md`). Or use the root orchestrator:
`npm run dev` at the repository root starts both.

## Checks

```bash
npm run lint       # eslint
npm run typecheck  # tsc --noEmit
npm run build      # production build (output: standalone)
```

## Configuration

Copy the relevant keys from the repository-root `.env.example` into
`.env.local`:

- `NEXT_PUBLIC_API_URL` — backend base URL (default `http://localhost:8000`)
- `NEXT_PUBLIC_APP_URL` — canonical site URL for metadata (default localhost)
