# Sprint 5C.1 — Multi-Scanner Orchestration Foundation

**Date:** 2026-08-19
**Status:** ✅ Complete
**Duration:** Single session

## Objective

Refactor the single-scanner analysis pipeline into a multi-scanner orchestration
architecture capable of running multiple independent security scanners within
a single AnalysisRun — without implementing any new scanners.

## What changed

### New domain model: ScannerRun

A `ScannerRun` tracks one scanner's execution within an `AnalysisRun`:

```
AnalysisRun  1 ──▶ * ScannerRun
```

Each ScannerRun has its own lifecycle (PENDING → RUNNING → terminal),
timing, finding count, and failure reason.

**Files created:**
- `app/models/scanner_run.py` — ORM model + `ScannerRunStatus` enum
- `app/domains/scanners/scanner_run_repository.py` — async CRUD + lifecycle helpers
- `app/domains/scanners/registry.py` — scanner name → provider factory registry
- `alembic/versions/20260819_0007_scanner_runs.py` — migration

### Orchestrator refactored for multi-scanner support

The orchestrator now supports two modes:

1. **Single-provider** (backward compatible): `provider` is set, `scanner_providers` is `None`
2. **Multi-scanner** (Sprint 5C.1): `scanner_providers` is a list of providers

The multi-scanner path creates a `ScannerRun` per configured scanner and executes
them sequentially, tracking each independently.

**Files modified:**
- `app/domains/analysis/orchestrator.py` — added `_execute_multi_scanner`, ScannerRun lifecycle
- `app/domains/analysis/ports.py` — `AnalysisExecutionContext` now includes `scanner_run_id`
- `app/core/config.py` — added `ANALYSIS_SCANNERS` and `scanner_timeout_seconds`
- `app/api/deps.py` — multi-scanner DI wiring via `parse_scanner_list` + `build_scanner`

### Configuration

New environment variable:

```bash
# Comma-separated list of scanners (overrides ANALYSIS_PROVIDER when set)
ANALYSIS_SCANNERS=trivy
```

## Architecture

```
AnalysisOrchestrator
    │
    ├── (single mode) AnalysisProvider.execute()
    │
    └── (multi mode) for each scanner in ANALYSIS_SCANNERS:
            ScannerRun(name=scanner)
                │
                └── ScannerProvider.execute()
```

**Provider registry pattern:**
```python
# app/domains/scanners/registry.py
_REGISTRY = {"trivy": _build_trivy}
# Future: gitleaks, semgrep, syft, grype
```

## Database changes

New table: `scanner_runs`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| analysis_run_id | UUID | FK → analysis_runs.id (CASCADE) |
| scanner_name | VARCHAR(32) | e.g. "trivy" |
| scanner_version | VARCHAR(32) | e.g. "0.54.0" |
| status | VARCHAR(16) | enum: pending/running/completed/failed/skipped/cancelled |
| started_at | TIMESTAMPTZ | nullable |
| completed_at | TIMESTAMPTZ | nullable |
| duration_ms | INTEGER | nullable |
| finding_count | INTEGER | nullable |
| component_count | INTEGER | nullable |
| failure_reason | VARCHAR(512) | nullable |

**Indexes:**
- `ix_scanner_runs_analysis_run_id`
- `ix_scanner_runs_status`
- `uq_scanner_runs_active_per_analysis` (partial unique: one active run per scanner per analysis)

## Backward compatibility

- Existing `ANALYSIS_PROVIDER=fake` still works via single-provider mode
- Existing `ANALYSIS_PROVIDER=trivy` still works via single-provider mode
- `ANALYSIS_SCANNERS` takes precedence when set
- API responses unchanged for existing endpoints

## How future scanners integrate

1. Implement the `AnalysisProvider` protocol (or `ScannerProvider`)
2. Register in `app/domains/scanners/registry.py`:
   ```python
   _REGISTRY["gitleaks"] = _build_gitleaks
   ```
3. Add to `ANALYSIS_SCANNERS=gitleaks`

**No changes to orchestrator, API, or database required.**

## Tests

**161 tests passing** (all existing + new)

New test files:
- `tests/unit/domains/scanners/test_trivy_provider_integration.py` — mocked workspace + provider
- `tests/unit/domains/scanners/test_github_source.py` — GitHub acquisition
- `tests/unit/domains/scanners/test_token_resolver.py` — token resolver wiring

## Validation

| Check | Result |
|---|---|
| Backend ruff | ✅ 0 errors |
| Backend format | ✅ 121 files |
| Backend pyright | ✅ 0 errors |
| Backend pytest (SQLite) | ✅ 161 passed |
| Alembic (SQLite) | ✅ 7 migrations |
| Frontend tsc | ✅ 0 errors |
| Frontend eslint | ✅ 0 warnings |
| Frontend vitest | ✅ 72 passed |
| Frontend build | ✅ |

## Security measures

- Token resolver isolation per owner
- Scanner execution timeout per scanner (separate from AnalysisRun timeout)
- ScannerRun status transitions validated at application level
- Partial unique index prevents duplicate active runs per scanner per analysis
- Existing Sprint 5B security guarantees preserved

## Known limitations

- Scanners execute sequentially (not parallel)
- No dependency-aware execution ordering
- No scanner-specific SBOM storage yet
- No findings `metadata_json` column yet (deferred to 5C.2+)

## Files changed

```
apps/backend/alembic/versions/20260819_0007_scanner_runs.py (NEW)
apps/backend/app/api/deps.py
apps/backend/app/core/config.py
apps/backend/app/domains/analysis/orchestrator.py
apps/backend/app/domains/analysis/ports.py
apps/backend/app/domains/scanners/registry.py (NEW)
apps/backend/app/domains/scanners/scanner_run_repository.py (NEW)
apps/backend/app/models/__init__.py
apps/backend/app/models/scanner_run.py (NEW)
apps/backend/tests/conftest.py
apps/backend/tests/unit/domains/scanners/test_github_source.py (NEW)
apps/backend/tests/unit/domains/scanners/test_token_resolver.py (NEW)
apps/backend/tests/unit/domains/scanners/test_trivy_provider_integration.py (NEW)
```

## Suggested next sprint

**Sprint 5C.2** — Additional security scanners (Gitleaks for secret scanning)
or **Sprint 5C.3** — Semgrep SAST integration

Both leverage the same registry + ScannerRun pattern established in 5C.1.
