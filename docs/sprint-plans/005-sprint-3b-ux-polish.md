# Sprint 3B — Repository Experience & UX Polish

> **Status:** ✅ Shipped — 2026-08-06

## Goal

The repository module already works (Sprint 3A). This sprint makes it feel
like a professional SaaS interface: a shareable list view with real search,
filters, sorting and pagination; information-dense cards; sectioned detail
pages; and friendly loading, empty and error states — without touching the
auth, the API contract beyond additive query params, or the database schema.

No DevSecOps features, no scanning, no AI, no prediction, no reports, no
background workers. This is purely presentation-layer polish.

## What changed

### Repository list (`/app/repositories`)

- **URL-persisted view state.** Search, every filter, sort key + direction,
  page and page-size serialize into the query string
  (`q`, `lang`, `vis`, `status`, `imported`, `archived`, `disabled`,
  `sort`, `order`, `page`, `per`) via `lib/repository-view.ts` — a pure
  parse/encode module (defaults are omitted so URLs stay short). Refresh,
  share and back/forward all restore the exact view. The page is wrapped in a
  `<Suspense>` boundary (required by `useSearchParams`).
- **Debounced search (350 ms)** with **search highlighting** — matches in the
  repo name, owner and description render inside `<mark>` via the pure
  `highlightSegments` helper (`lib/search.ts`) and the `<SearchHighlight>`
  component.
- **Advanced filters:** language, visibility, analysis status, imported
  recency (7/30/90 days), archived (any/yes/no), disabled (any/yes/no).
- **Sorting:** name, stars, forks, language, size, last push, last updated,
  recently imported — plus an explicit asc/desc toggle that snaps to the
  natural direction when a new key is picked.
- **Pagination:** numbered page buttons with ellipsis windowing
  (`pageNumberList`), Previous/Next, a results-per-page selector
  (12/24/48) and a "Showing X repositories · page Y of Z" summary.
- **Unified page reset** — every filter/search/sort/page-size change returns
  to page 1; only explicit page jumps keep the page.

### Repository cards

- Memoized (`React.memo`) with stable callbacks from the parent so only the
  syncing card re-renders.
- New content: **topic chips** (3 visible + "+n more"), **open issues**
  stat, **imported/synced** timestamps, language badge with a GitHub-style
  color dot, and search highlighting on name/owner/description.
- Hover lift + ring accent, `focus-within` ring, keyboard-accessible name
  link and actions menu, and a responsive stat grid (2 columns on mobile,
  4 on desktop).

### Repository details (`/app/repositories/[id]`)

- **Copy repository URL** and **Copy clone URL** actions with clipboard
  feedback, plus the existing Open in GitHub.
- Reorganized into labelled sections: **General information**, **Statistics**,
  **Analysis information** (status, health score "—", last analysis
  "Never"), **Repository metadata** (full name, provider ID, tracked since,
  last synced, updated, archived/disabled, repository URL), **License**, and
  **Topics**.

### States

- **Empty states** (`RepositoryEmptyState`): no repositories yet (with the
  import dialog), no filter matches (with a Clear-filters action), and the
  no-GitHub-connection gate inside the import dialog.
- **Loading**: skeleton cards (list) and a skeleton detail page — no generic
  spinners.
- **Error states** (`RepositoryErrorState`) map backend error codes to
  friendly copy and the right action via `lib/repository-errors.ts`:
  `github_rate_limited` → retry, `github_token_invalid` / `github_not_connected`
  / `github_forbidden` → Reconnect GitHub link, `not_found` → explain,
  network failure → retry. Unknown codes fall back to a generic message that
  still shows the backend detail.

### Backend (additive only — one genuine contract gap)

`GET /repositories` gained three backward-compatible query params and three
sort keys, because server-side filtering is the only way to keep them
consistent with pagination:

- `archived` / `disabled` (tri-state booleans) and `imported_after` (ISO
  timestamp; "imported" = when EvoShield started tracking, `created_at`).
- `sort` now also accepts `forks`, `language`, `size_kb`.

No new endpoints, no schema change, no auth changes. Existing behavior for
absent params is unchanged (older clients keep working).

### Performance & accessibility

- Import dialog is lazy-loaded (`next/dynamic`, `ssr: false`) — the GitHub
  browse flow is only fetched when first opened.
- Request sequencing (`requestSeq` + cancelled flags) prevents out-of-order
  responses from clobbering newer views.
- ARIA labels on every filter, `aria-current="page"` on pagination,
  `role="alert"` on errors, focus-visible rings throughout, screen-reader
  copy for icon-only controls.

## Frontend testing (new infrastructure)

There was no frontend test runner. Introduced the standard minimal setup:

- **Vitest + React Testing Library + jsdom + jest-dom** (`vitest.config.mts`,
  `src/test/setup.ts` with RTL cleanup, `npm test`).
- **57 focused tests** across pure logic and presentational components:
  - `lib/repository-view.test.ts` — URL parse/encode round-trips, invalid
    fallbacks, param mapping (tri-states → booleans, recency → ISO).
  - `lib/search.test.ts` — highlight segmentation (case-insensitive,
    multiple matches, round-trip).
  - `lib/format.test.ts` — compact numbers, relative time, dates.
  - `lib/repository-errors.test.ts` — error-code mapping.
  - `repository-pagination.test.tsx` — page windowing, disabled states,
    callbacks.
  - `repository-card.test.tsx`, `repository-empty-state.test.tsx`,
    `repository-error-state.test.tsx`, `search-highlight.test.tsx`.
- CI (`backend-postgres` untouched; `frontend` job) gained a `npm test`
  (vitest) step between typecheck and build.

## Validation

| Check | Result |
| --- | --- |
| Backend ruff (check + format) | ✅ clean |
| Backend pyright | ✅ 0 errors |
| Backend pytest — SQLite | ✅ 74 passed |
| Backend pytest — PostgreSQL 16/18 (fresh cluster, migrations applied) | ✅ 74 passed |
| Frontend vitest | ✅ 57 passed |
| Frontend `tsc --noEmit` | ✅ 0 errors |
| Frontend eslint | ✅ 0 warnings |
| Frontend `next build` | ✅ green |

## Files

**Backend (additive)**
- `app/api/routers/repositories.py` — new list query params + sort keys
- `app/domains/github/service.py`, `app/domains/github/repository.py` — pass-through
- `tests/integration/test_repositories_api.py` — filter/sort coverage (74 total)

**Frontend**
- `lib/repository-view.ts`, `lib/search.ts`, `lib/repository-errors.ts`
- `components/repositories/`: `repository-toolbar.tsx`, `repository-pagination.tsx`,
  `repository-empty-state.tsx`, `repository-error-state.tsx`,
  `search-highlight.tsx`, rewritten `repository-card.tsx`
- Rewritten `app/app/repositories/page.tsx`, polished `app/app/repositories/[id]/page.tsx`
- `vitest.config.mts`, `src/test/setup.ts`, `src/test/fixtures.ts`, 9 test files
- `.github/workflows/ci.yml` — vitest step

## Definition of done

A user can login → connect GitHub → browse → search → filter → sort →
paginate → import → refresh → delete → view details, with a polished,
responsive, accessible experience and the exact view persisted in the URL.

**Awaiting approval before Sprint 4** (the `analysis` domain).
