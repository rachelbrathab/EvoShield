# EvoShield 🔬🛡️

**Predictive Software Supply Chain Risk Assessment Using Temporal Repository Intelligence**

EvoShield is a DevSecOps SaaS platform that connects GitHub repositories, runs
industry-grade supply chain security scans, tracks risk over time, and predicts
where risk is heading — so developers can remediate before attackers exploit it.

> Final year engineering project. Built one sprint at a time, like a real
> software company: plan → approve → implement → verify.

## Monorepo layout

```
evoshield/
├── apps/
│   ├── frontend/   Next.js 16 · React 19 · TypeScript · Tailwind v4 · shadcn/ui
│   └── backend/    FastAPI · Python 3.12 · SQLAlchemy async · Alembic
├── packages/       Shared workspace packages (future: SDK, contracts)
├── docs/           Architecture, sprint plans, ADRs
├── research/       Tool & approach research notes
├── scripts/        Dev tooling (setup.sh, dev.sh)
└── .github/        CI workflow
```

## Tech stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, Recharts (Sprint 8) |
| Backend | FastAPI, Python 3.12 (uv-managed), async SQLAlchemy |
| Database | Supabase PostgreSQL (prod) / SQLite (local dev fallback) |
| Auth | Identity domain — Supabase Auth (prod) + local provider (dev) |
| Security tools | Trivy · Syft · Grype · Semgrep · Gitleaks (Sprint 5) |
| Prediction | pandas · NumPy · scikit-learn (Sprint 7) |
| Deployment | Render |

See [docs/architecture.md](docs/architecture.md) for the full picture,
`docs/sprint-plans/` for the roadmap, and
[docs/reviews/sprint-1-production-readiness.md](docs/reviews/sprint-1-production-readiness.md)
for the post-sprint production-readiness review.

## Quick start

```bash
npm run setup         # installs frontend deps + syncs backend env + migrates
npm run dev           # runs frontend (:3000) and backend (:8000) concurrently
```

Then open:

- App:       http://localhost:3000
- API docs:  http://localhost:8000/docs
- Health:    http://localhost:8000/api/v1/health

Per-service instructions live in `apps/frontend/README.md` and
`apps/backend/README.md`.

Frontend tests (Vitest + React Testing Library): `cd apps/frontend && npm test`.

## Sprint reports

Every sprint ships a report in `docs/sprint-plans/` — goal, architecture
review, files, acceptance criteria and validation:

| Report | Sprint |
| --- | --- |
| `001-sprint-1-project-setup.md` | 1 — project setup |
| `002-sprint-2-authentication.md` | 2 — authentication |
| `003-analysis-status-foundation.md` | 3 prep — analysis-status foundation |
| `004-sprint-3a-repository-integration.md` | 3A — repository integration |
| `005-sprint-3b-ux-polish.md` | 3B — repository UX polish |
| `006-sprint-4a-analysis-infrastructure.md` | 4A — analysis infrastructure |
| `007-sprint-5a-scanner-foundation-trivy.md` | 5A — scanner foundation + Trivy |
| `008-sprint-5b-repository-acquisition.md` | 5B — repository acquisition & scan execution |
| `009-sprint-5c1-multi-scanner-orchestration.md` | 5C.1 — multi-scanner orchestration foundation |
| `010-sprint-5c2-gitleaks.md` | 5C.2 — Gitleaks secret detection |
| `011-sprint-5c3-semgrep-sast.md` | 5C.3 — Semgrep SAST |

## Sprint roadmap

| Sprint | Focus | Status |
| --- | --- | --- |
| 1 | Project setup — monorepo, CI, landing page | ✅ done |
| 2 | Authentication — identity domain, JWT sessions, GitHub OAuth | ✅ done |
| 3 (prep) | Analysis-status foundation — `repositories` table, status enum, badge | ✅ done |
| 3A | Repository integration — GitHub connect, import, sync, browse, detail | ✅ done |
| 3B | Repository UX polish — URL-persisted search/filter/sort/pagination, cards, states, Vitest | ✅ done |
| 4A | Analysis infrastructure — `analysis_runs` history, orchestrator state machine, provider port + fake adapter, run history/timeline UI | ✅ done |
| 5A | Scanner foundation + Trivy — normalized findings, Trivy adapter, findings API/UI, subprocess safety | ✅ done |
| 5B | Repository acquisition & scan execution — GitHub clone, workspace lifecycle, token security | ✅ done |
| 5C.1 | Multi-scanner orchestration — ScannerRun model, provider registry, sequential execution | ✅ done |
| 5C.2 | Gitleaks secret detection — secret scanning, redaction, multi-scanner pipeline | ✅ done |
| 5C.3 | Semgrep SAST — static analysis, CWE/OWASP metadata, source code safety | ✅ done |
| 6 | Repository intelligence | planned |
| 7 | Prediction engine | planned |
| 8 | Dashboard | planned |
| 9 | Reports | planned |
| 10 | AI security assistant | planned |
| 11 | Renovate integration | planned |
| 12 | Optimization | planned |
| 13 | Testing & hardening | planned |
| 14 | Deployment (Render) | planned |

## Development principles

- Clean architecture with explicit layers (api → domains → repositories → models)
- SOLID, async-first, typed end-to-end (Python type hints, TypeScript strict)
- Environment-driven configuration, no hardcoded secrets
- Structured logging and a shared exception taxonomy
- Every sprint ships with acceptance criteria + tests + docs
- Backend: pytest on SQLite locally and PostgreSQL in CI; frontend: Vitest
  component/unit tests for pure logic and key UI states
