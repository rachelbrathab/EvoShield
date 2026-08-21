# Sprint 6 — Repository Intelligence

- **Date:** 2026-08-20
- **Duration:** Single session
- **Status:** ✅ Complete

## Goal

Turn scanner evidence into actionable repository intelligence — risk scoring, finding aggregation, prioritization, trend analysis, and scanner coverage.

## Architecture

```
Repository
    ↓
Latest AnalysisRun
    ↓
ScannerRuns (trivy, gitleaks, semgrep, grype)
    ↓
Findings
    ↓
IntelligenceService
    ├── Finding Aggregation (by severity, type, scanner)
    ├── Risk Scoring (deterministic heuristic, 0-100)
    ├── Risk Factors (categorized explanations)
    ├── Finding Prioritization (what to fix first)
    ├── Trend Analysis (improving / worsening / unchanged)
    └── Scanner Coverage (completed / failed / skipped)
    ↓
RepositoryIntelligence Response
```

## Key Decisions

1. **Dynamic computation** — no new database tables. Intelligence is computed on-the-fly from existing Finding, AnalysisRun, and ScannerRun data.
2. **Transparent heuristic** — risk score is deterministic, explainable, bounded [0-100]. NOT a validated security standard.
3. **Conservative approach** — no cross-scanner deduplication in this sprint. Each finding preserves scanner provenance.
4. **Intelligence domain** — `app/domains/intelligence/` as a separate bounded context.

## Files Created/Modified

| File | Change |
|------|--------|
| `app/domains/intelligence/__init__.py` | **Created** — domain documentation |
| `app/domains/intelligence/scoring.py` | **Created** — risk scoring engine |
| `app/domains/intelligence/schemas.py` | **Created** — API response contracts |
| `app/domains/intelligence/service.py` | **Created** — intelligence computation service |
| `app/api/routers/intelligence.py` | **Created** — API endpoint |
| `app/api/router.py` | Modified — intelligence router registered |
| `tests/unit/domains/intelligence/test_scoring.py` | **Created** — 26 scoring tests |
| `tests/unit/domains/intelligence/test_service.py` | **Created** — 21 service/API tests |
| `frontend/src/lib/intelligence.ts` | **Created** — frontend types |
| `frontend/src/lib/intelligence-api.ts` | **Created** — frontend API client |
| `frontend/src/components/analysis/intelligence-section.tsx` | **Created** — intelligence UI component |
| `frontend/src/app/app/analysis/[id]/page.tsx` | Modified — intelligence section integrated |
| `docs/adr/0015-repository-intelligence.md` | **Created** |
| `docs/sprint-plans/013-sprint-6-repository-intelligence.md` | **Created** |

## Validation

| Check | Result |
|---|---|
| Backend ruff format | ✅ 151 files |
| Backend ruff check | ✅ All passed |
| Backend pyright | ✅ 0 errors, 0 warnings |
| Backend pytest (SQLite) | ✅ **407 passed** (was 360) |
| Frontend lint | ✅ Clean |
| Frontend vitest | ✅ **72 passed** |
| Frontend build | ✅ Success |

## Test Breakdown

| Test file | Tests |
|-----------|-------|
| test_scoring.py | 26 (bounds, weights, determinism, risk levels, aggregation, counts) |
| test_service.py | 21 (ownership, aggregation, risk factors, prioritization, trend, coverage, summary, API) |
| **Total new** | **47** |

## Risk Scoring Formula

```
risk_score = clamp(100 - Σ(severity_weight × count) - secret_penalty - unfixed_penalty, 0, 100)
```

| Severity | Weight |
|----------|--------|
| Critical | 25 |
| High | 15 |
| Medium | 8 |
| Low | 2 |
| Unknown | 1 |

Secret penalty: 20 (flat)
Unfixed vuln penalty: 5 per vuln

## Security Audit

- ✅ No raw scanner output in intelligence response
- ✅ No secret values in risk factors or summaries
- ✅ No source code snippets
- ✅ Owner scoping enforced at API boundary
- ✅ No logger calls in intelligence service
- ✅ Deterministic computation (same inputs → same output)

## Known Limitations

1. **Risk score is a heuristic** — not a validated security standard
2. **No cross-scanner deduplication** — Trivy + Grype may show duplicate CVEs
3. **No persistence** — intelligence is recomputed per request
4. **Trend limited to most recent** — no historical trend visualization
5. **PostgreSQL not validated** — only SQLite test suite was run

**Sprint 6 is done. Awaiting approval before Sprint 7 (Prediction Engine).**
