# Sprint 5A — Security Scanner Foundation + Trivy

> **Status:** ✅ Shipped — 2026-08-19

## Goal

Transform EvoShield from an analysis lifecycle platform into a platform
capable of performing its **first real security analysis**.  Integrate
Trivy behind the existing `AnalysisProvider` abstraction, with a normalized
findings model that every future scanner will reuse.

## What Was Implemented

### Scanner Domain (`domains/scanners/`)

- **`enums.py`** — `Severity` (unknown/low/medium/high/critical) and
  `FindingType` (vulnerability/secret/sast/license/configuration/sbom) enums
- **`ports.py`** — `ScannerProvider` protocol, `ScannerFinding` dataclass,
  `FindingParser` protocol
- **`workspace.py`** — `ScannerWorkspace` temporary directory manager with
  async context manager and guaranteed cleanup
- **`repository.py`** — `FindingRepository` with owner-scoped queries,
  severity/type filtering, pagination

### Trivy Adapter (`domains/scanners/providers/trivy/`)

- **`runner.py`** — `TrivyRunner` with safe subprocess execution:
  - `asyncio.create_subprocess_exec()` (never `shell=True`)
  - Explicit argument arrays — no shell interpretation
  - Path validation (absolute, exists, is directory)
  - Timeout enforcement
  - Exit code and stderr capture
- **`parser.py`** — `TrivyResultParser` converting Trivy JSON output to
  `ScannerFinding` objects with severity mapping and field normalization
- **`provider.py`** — `TrivyProvider` implementing `AnalysisProvider`:
  - Availability detection
  - Version detection
  - Filesystem scan execution
  - Findings persistence via callback
  - Cancellation support

### Database

- **`findings` table** (migration `0006_findings.py`):
  - `id` (UUID PK), `created_at`, `updated_at`
  - `analysis_run_id` (FK → analysis_runs, CASCADE)
  - `scanner`, `scanner_version`
  - `finding_type` (enum-as-VARCHAR)
  - `severity` (enum-as-VARCHAR)
  - `title`, `description`
  - `package_name`, `installed_version`, `fixed_version`
  - `vulnerability_id`, `references_json`, `location`
  - Indexes on: analysis_run_id, severity, finding_type, vulnerability_id

### API Endpoints

- `GET /analysis/{id}/findings` — list findings for a run (paginated,
  severity/type filtered, owner-scoped)
- `GET /analysis/repositories/{id}/findings` — list findings for all
  runs of a repository (owner-scoped)

### Frontend

- **`findings.ts`** — TypeScript types, severity/type metadata
- **`findings-api.ts`** — API client for findings endpoints
- **`finding-severity-badge.tsx`** — colored severity badge
- **`findings-section.tsx`** — findings list with filters, empty state,
  loading skeletons, error handling, live polling during active runs
- **Analysis detail page** — updated to include `<FindingsSection>`

### Configuration

- `ANALYSIS_PROVIDER=trivy` selects the real scanner
- `TRIVY_EXECUTABLE` and `TRIVY_TIMEOUT_SECONDS` settings
- `.env.example` updated with Trivy settings

## Architecture Changes

```
Before (Sprint 4A):
  AnalysisOrchestrator → AnalysisProvider → FakeAnalysisProvider

After (Sprint 5A):
  AnalysisOrchestrator → AnalysisProvider → TrivyProvider
                                               ↓
                                          TrivyRunner (subprocess)
                                               ↓
                                          TrivyResultParser
                                               ↓
                                          ScannerFinding[]
                                               ↓
                                          FindingRepository → findings table
```

The orchestrator is **unchanged**.  Trivy is a drop-in adapter.

## Security Measures

1. **No shell=True** — all subprocess calls use `create_subprocess_exec`
2. **Argument arrays** — no string concatenation into commands
3. **Path validation** — absolute paths only, existence and type checks
4. **Timeout enforcement** — configurable per-scanner timeout
5. **Owner scoping** — all findings queries enforce ownership chain
6. **Error sanitization** — raw subprocess stderr not exposed to users
7. **Malicious input tests** — test suite verifies path traversal, shell
   metacharacters, and other injection attempts cannot reach the shell

## Tests

### New Tests (34 total)

**Trivy Parser (11 tests):**
- Empty output, empty results, no vulnerabilities
- Single vulnerability parsing
- Severity mapping (CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN)
- Missing required fields, optional fields
- Multiple results, invalid JSON
- Reference deduplication, title truncation

**Trivy Runner (6 tests):**
- Availability detection (available/unavailable)
- Version detection (success/unavailable/error)
- Path validation (nonexistent/relative/file-not-directory)

**Scanner Workspace (5 tests):**
- Creation, cleanup, idempotent cleanup
- Pre-entry path error, path type verification

**Findings Repository (6 tests):**
- Create many findings
- Severity filtering
- Repository-scoped listing
- Owner scoping (alice/bob isolation)
- Empty results

**Backend Integration:**
- All 94 existing tests pass (no regressions)
- PostgreSQL migration applies cleanly

### Validation Results

| Check | Result |
|---|---|
| Backend ruff | ✅ 0 errors |
| Backend ruff format | ✅ 111 files formatted |
| Backend pyright | ✅ 0 errors, 0 warnings |
| Backend pytest (SQLite) | ✅ **128 passed** |
| Backend pytest (PostgreSQL) | ✅ **128 passed** |
| Alembic (SQLite) | ✅ 6 migrations applied |
| Alembic (PostgreSQL) | ✅ 6 migrations applied |
| Frontend tsc | ✅ 0 errors |
| Frontend eslint | ✅ 0 errors, 0 warnings |
| Frontend vitest | ✅ **72 passed** |
| Frontend next build | ✅ Production build succeeds |

## Known Limitations

1. **No repository cloning yet** — Trivy scans a filesystem path; when
   cloning is implemented (Sprint 5B+), the workspace will contain the
   cloned checkout
2. **No container scanning** — only filesystem vulnerability scanning
3. **No secret scanning** — Gitleaks integration is a later sprint
4. **No SAST** — Semgrep integration is a later sprint
5. **No SBOM generation** — Syft integration is a later sprint
6. **Trivy must be installed** — the backend detects unavailability and
   returns a clear `scanner_unavailable` error

## Deferred Work

- Repository cloning for full filesystem scans
- Trivy container image scanning
- Gitleaks secret scanning
- Semgrep SAST
- Syft SBOM generation
- Grype dependency vulnerability matching
- Findings analytics and dashboards
- Risk scoring based on findings

## Files Changed

### New Files (17)
- `apps/backend/app/domains/scanners/enums.py`
- `apps/backend/app/domains/scanners/ports.py`
- `apps/backend/app/domains/scanners/workspace.py`
- `apps/backend/app/domains/scanners/repository.py`
- `apps/backend/app/domains/scanners/providers/trivy/__init__.py`
- `apps/backend/app/domains/scanners/providers/trivy/provider.py`
- `apps/backend/app/domains/scanners/providers/trivy/runner.py`
- `apps/backend/app/domains/scanners/providers/trivy/parser.py`
- `apps/backend/app/models/finding.py`
- `apps/backend/alembic/versions/20260806_0006_findings.py`
- `apps/backend/app/api/routers/findings.py`
- `apps/backend/tests/unit/domains/scanners/__init__.py`
- `apps/backend/tests/unit/domains/scanners/test_trivy_parser.py`
- `apps/backend/tests/unit/domains/scanners/test_trivy_runner.py`
- `apps/backend/tests/unit/domains/scanners/test_workspace.py`
- `apps/backend/tests/unit/domains/scanners/test_findings_repository.py`
- `apps/frontend/src/lib/findings.ts`
- `apps/frontend/src/lib/findings-api.ts`
- `apps/frontend/src/components/analysis/finding-severity-badge.tsx`
- `apps/frontend/src/components/analysis/findings-section.tsx`
- `docs/adr/0009-security-scanner-architecture.md`

### Modified Files (7)
- `apps/backend/app/models/__init__.py` — added Finding, Severity, FindingType exports
- `apps/backend/app/core/config.py` — added Trivy settings
- `apps/backend/app/domains/analysis/factory.py` — added Trivy provider selection
- `apps/backend/app/api/router.py` — registered findings router
- `apps/backend/app/api/deps.py` — wired findings persistence callback
- `apps/backend/app/domains/scanners/__init__.py` — updated with exports
- `apps/frontend/src/app/app/analysis/[id]/page.tsx` — added FindingsSection
- `apps/backend/.env.example` — added Trivy settings

## Suggested Next Sprint

**Sprint 5B — Repository Cloning + Extended Scanning**

The current Trivy integration has a placeholder for filesystem path.
Sprint 5B should implement:
1. Safe repository cloning (git clone into temporary workspace)
2. Full filesystem vulnerability scanning with real repo content
3. Trivy container image scanning (optional)
4. Scan result caching

Or **Sprint 6 — Repository Intelligence** if scanning is considered complete
for the MVP scope.
