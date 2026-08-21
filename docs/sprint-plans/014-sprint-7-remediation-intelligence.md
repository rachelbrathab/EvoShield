# Sprint 7 — Remediation Intelligence

## Status

✅ Complete

## Objective

Evolve EvoShield from "we detected security problems" to "we detected
security problems, explain why they matter, tell the developer what to do,
identify whether a fix exists, track remediation state, and show whether
security is improving."

## What was built

### Remediation Domain (`app/domains/remediation/`)

- **enums.py** — `FindingStatus` (OPEN/ACKNOWLEDGED/RESOLVED/FALSE_POSITIVE),
  `FixAvailability` (FIX_AVAILABLE/NO_KNOWN_FIX/NOT_APPLICABLE/UNKNOWN)
- **repository.py** — `FindingStatusRepository` with owner-scoped queries
- **guidance.py** — Deterministic rule-based guidance per finding type
- **service.py** — `RemediationService` computing full remediation intelligence
- **schemas.py** — API response contracts (`AnalysisRemediation`, `FindingRemediation`, etc.)

### FindingStatus Model (`app/models/finding_status.py`)

Separate table for mutable finding lifecycle state. The Finding model
remains immutable (scanner-produced data). Default: OPEN.

### Migration (`0008_finding_statuses`)

Creates `finding_statuses` table with:
- finding_id (FK to findings, unique, cascade delete)
- status (VARCHAR, default 'open')
- set_by_user_id (FK to users, nullable)
- note (optional text)
- created_at / updated_at (timestamps)

### API Endpoints (`app/api/routers/remediation.py`)

1. `GET /analysis/{id}/remediation` — full remediation intelligence
2. `GET /analysis/{id}/findings/{fid}/remediation` — single finding details
3. `PATCH /analysis/{id}/findings/{fid}/status` — update status

### Intelligence Integration

`RepositoryIntelligence` response now includes `RemediationMetrics`:
- open / acknowledged / resolved / false_positive counts
- fixable count
- remediation rate

### Frontend

- `lib/remediation.ts` — types and display metadata
- `lib/remediation-api.ts` — API client
- `components/analysis/remediation-section.tsx` — Remediation plan UI
  - Summary cards (open/acknowledged/resolved/rate)
  - Per-finding remediation with expandable guidance
  - Status update actions (acknowledge, resolve)
  - Fix availability badges
- Analysis page updated to include RemediationSection

## Architecture decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Status storage | Separate table | Finding model is immutable scanner data |
| Default status | OPEN (absent row) | Zero-migration for existing findings |
| Guidance engine | Deterministic rules | No LLM, no ML, testable, explainable |
| Priority formula | Weighted composite | Deterministic, transparent |
| Intelligence | Included in existing response | No new endpoint needed for metrics |
| Frontend | Expandable per-finding cards | Progressive disclosure |

## Files changed

| File | Change |
|------|--------|
| `app/domains/remediation/__init__.py` | **Created** |
| `app/domains/remediation/enums.py` | **Created** |
| `app/domains/remediation/guidance.py` | **Created** |
| `app/domains/remediation/repository.py` | **Created** |
| `app/domains/remediation/schemas.py` | **Created** |
| `app/domains/remediation/service.py` | **Created** |
| `app/models/finding_status.py` | **Created** |
| `app/api/routers/remediation.py` | **Created** |
| `app/api/router.py` | Modified — router registered |
| `app/domains/intelligence/schemas.py` | Modified — RemediationMetrics added |
| `app/domains/intelligence/service.py` | Modified — remediation metrics computed |
| `alembic/versions/..._0008_finding_statuses.py` | **Created** |
| `tests/unit/domains/remediation/__init__.py` | **Created** |
| `tests/unit/domains/remediation/test_guidance.py` | **Created** — 10 tests |
| `tests/unit/domains/remediation/test_service.py` | **Created** — 21 tests |
| `frontend/src/lib/remediation.ts` | **Created** |
| `frontend/src/lib/remediation-api.ts` | **Created** |
| `frontend/src/components/analysis/remediation-section.tsx` | **Created** |
| `frontend/src/app/app/analysis/[id]/page.tsx` | Modified — section integrated |

## Validation

| Check | Result |
|-------|--------|
| Backend ruff format | ✅ 163 files |
| Backend ruff check | ✅ All passed |
| Backend pyright | ✅ 0 errors, 0 warnings |
| Backend pytest (SQLite) | ✅ **438 passed** |
| Frontend lint | ✅ Clean |
| Frontend vitest | ✅ **72 passed** |
| Frontend build | ✅ Success |
| PostgreSQL | ❌ Not validated locally (CI only) |

## Security guarantees

- ✅ No raw scanner output in remediation responses
- ✅ No secret values in guidance or status responses
- ✅ No source code snippets
- ✅ Owner scoping enforced at API boundary
- ✅ FindingStatus table properly FK-constrained
- ✅ Secret sentinel test passes (SUPER_SECRET_TEST_VALUE not in response)

## Known limitations

1. PostgreSQL not validated locally (CI only)
2. No cross-analysis remediation correlation
3. No automatic resolution (user-initiated only)
4. No notification system
5. No bulk status updates
