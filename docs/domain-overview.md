# Domain Overview

Each folder under `app/domains/` is a self-contained business domain. This
document describes what each owns, what it consumes, and when it ships.

## Principles

- **One domain, one responsibility.** No domain imports another.
- **Ports before tools.** Domains depend on ports (interfaces) defined by the
  domain; concrete implementations (scanner binaries, GitHub API, LLM vendor)
  are injected — so swapping a tool never rewrites a domain.
- **Orchestration outside domains.** Cross-domain flows live in `workers/` and
  the API layer.

## Domain table

| Domain | Ships (Sprint) | Owns | Consumes | Produces |
| --- | --- | --- | --- | --- |
| `identity` | 2 ✅ | Register/login/logout, JWT sessions, GitHub OAuth, user profiles | Supabase Auth / local provider (behind port) | Authenticated user + session |
| `health` | 1 ✅ | Liveness + dependency probes | Database | Health payload |
| `github` | 3 | GitHub OAuth, API client, repo metadata ingestion, repository contract (`RepositoryRead` incl. analysis status) | GitHub API (external) | Normalized repository data |
| `analysis` | 4 | Repo structure, manifests, metadata analysis, `analysis_runs` history | Repository data (via orchestration) | Analysis artifacts |
| `scanners` | 5 | Trivy/Syft/Grype/Semgrep/Gitleaks execution, finding normalization | Analysis artifacts | Unified `Finding` model |
| `intelligence` | 6 | Temporal risk tracking, trend features | Findings over time | Feature vectors |
| `prediction` | 7 | scikit-learn models, 90-day forecasts | Intelligence features | Risk scores + confidence |
| `recommendation` | 8 | Remediation guidance | Findings + predictions | Prioritized recommendations |
| `reports` | 9 | Report generation/export | All domains (via orchestration) | PDF/HTML/CSV |
| `chat` | 10 | AI assistant, grounding | Findings/predictions/recommendations | Conversational answers |

## Data flow (pipeline)

```
GitHub ──▶ Analysis ──▶ Scanners ──▶ Intelligence ──▶ Prediction
                                    │                    │
                                    └────────▶ Recommendation ──▶ Reports
                                                          │
                                                          └──▶ Chat
```

## Per-domain detail

### health (reference implementation)
The smallest complete domain and the pattern every other domain follows:
`service.py` (logic) + `schemas.py` (contract) + a router adapter. The
database probe accepts an injectable engine, which is why it has real unit
tests (`tests/unit/domains/health/`).

### identity (Sprint 2)
Authentication is its own bounded context: an `AuthProvider` port with two
adapters (local argon2+JWT for dev/test, Supabase for production) and GitHub
OAuth. Because the domain depends on a port, switching or adding identity
backends never rewrites other domains (ADR 0005).

### github (Sprint 3)
Defines the **source-provider port** so GitLab, Bitbucket and Azure DevOps
can be added as sibling providers implementing the same interface — no
downstream domain changes required (see `docs/module-dependency.md`).

### Analysis status (Sprint 3 preparation)
Every repository carries one *current* analysis lifecycle state
(`not_analyzed · queued · analyzing · analyzed · failed · cancelled`) — an
enum-backed VARCHAR on the `repositories` table (see `docs/adr/0006-analysis-status.md`).
It ships **before** any scanner so Sprint 3 ingestion and Sprint 4/5
pipelines both integrate against a stable, already-migrated schema. The
`RepositoryRead` contract exposes the status, and the frontend
`AnalysisStatusBadge` renders it — repository cards and detail pages drop it
in with zero redesign. Scan-specific data stays off the repository row:
scanners report progress by flipping `analysis_status` and write findings to
their own tables (Sprint 5).

### scanners (Sprint 5)
Scanner binaries are external infrastructure. The domain defines a
`Scanner` port; each tool (Trivy, Syft, …) is an adapter. Findings are
normalized into one `Finding` schema so downstream domains are tool-agnostic.

### prediction (Sprint 7)
Owns the model lifecycle: feature engineering, training, evaluation and
inference. Predictions include confidence intervals and feature attribution.

### chat (Sprint 10)
The AI assistant is a consumer, not a controller — it reads
findings/predictions/recommendations through the orchestration layer, never
bypassing the domains' own contracts.
