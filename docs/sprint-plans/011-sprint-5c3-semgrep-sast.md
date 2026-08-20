# Sprint 5C.3 — Semgrep SAST

## Objective

Integrate Semgrep as the third real security scanner behind the existing `ScannerRun` and provider registry architecture, with **mandatory source code safety** as the primary security requirement.

## What Was Implemented

### 1. Semgrep Provider (`app/domains/scanners/providers/semgrep/`)

Four files following the established Trivy/Gitleaks pattern:

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `runner.py` | Safe subprocess execution — `create_subprocess_exec` with argument arrays, timeout enforcement |
| `parser.py` | JSON output parsing with **mandatory source code safety** — `extra.lines`, `metavars`, `fixes` discarded |
| `provider.py` | `AnalysisProvider` adapter — orchestrates acquisition → execution → parsing → persistence → cleanup |

### 2. Scanner Registry Update

- `app/domains/scanners/registry.py` — Semgrep registered alongside Trivy and Gitleaks
- `app/core/config.py` — `semgrep_timeout_seconds` and `semgrep_config` configuration settings

### 3. Comprehensive Test Suite

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_semgrep_parser.py` | 18 | Source code safety (2 tests), severity mapping (4), CWE/OWASP extraction (2), edge cases (10) |
| `test_semgrep_runner.py` | 10 | Exit codes (3), availability (3), path validation (4), subprocess execution (1) |
| `test_semgrep_provider.py` | 14 | Registration (3), execution lifecycle (7), supports (3), error safety (1) |
| `test_semgrep_multiscanner.py` | 9 | Registry (4), configuration parsing (5) |

**Total new tests: 51**

### 4. Documentation

- `docs/adr/0013-semgrep-sast.md` — Architecture Decision Record
- This sprint report

## Architecture Changes

### Before

```
ANALYSIS_SCANNERS=trivy,gitleaks
    ├── ScannerRun(trivy)
    │       └── TrivyProvider
    └── ScannerRun(gitleaks)
            └── GitleaksProvider
```

### After

```
ANALYSIS_SCANNERS=trivy,gitleaks,semgrep
    ├── ScannerRun(trivy)
    │       └── TrivyProvider
    ├── ScannerRun(gitleaks)
    │       └── GitleaksProvider
    └── ScannerRun(semgrep)
            └── SemgrepProvider
```

### Scanner Provider Pattern

```
AnalysisOrchestrator
    └── ScannerRun(name="semgrep")
            └── SemgrepProvider.execute(context)
                    ├── GitHubRepositorySource.acquire()  ← reuse
                    ├── ScannerWorkspace                  ← reuse
                    ├── SemgrepRunner.run_scan()
                    │       └── semgrep scan --json --config auto --quiet <path>
                    ├── SemgrepResultParser.parse()
                    │       └── source code snippets DISCARDED (source safety)
                    ├── FindingRepository.create()         ← normalized findings
                    └── workspace.cleanup()
```

## Security Guarantees

| Guarantee | Evidence |
|-----------|----------|
| **No source code in database** | Parser discards `extra.lines`, `metavars`, `fixes` — `test_source_snippet_not_in_finding` |
| **No source code in API responses** | Findings contain only title, description, location, CWE/OWASP |
| **No source code in logs** | Parser `logger.info()` only logs count + run ID |
| **No source code in errors** | Provider errors use safe codes — `test_stderr_not_in_error_message` |
| **No source code in frontend** | Findings UI shows rule, file, line — never source snippets |
| **No shell=True** | `create_subprocess_exec` with argument arrays — `test_no_shell_true` |
| **Workspace cleanup** | `finally` block always cleans up — `test_workspace_cleanup_on_success/failure` |
| **Timeout enforcement** | `asyncio.wait_for` with configurable timeout — `test_timeout_kills_process` |

## Validation Results

| Check | Result |
|-------|--------|
| Backend ruff format | ✅ 137 files formatted |
| Backend ruff check | ✅ All checks passed |
| Backend pyright | ✅ 0 errors, 0 warnings |
| Backend pytest | ✅ **289 passed** (was 224) |
| Frontend lint | ✅ No issues |
| Frontend vitest | ✅ 72 passed |
| Frontend build | ✅ Success |

### Test Breakdown

| Category | Count |
|----------|-------|
| Scanner tests | 195 |
| Other backend tests | 94 |
| **Total** | **289** |

## Semgrep Exit Code Semantics

Semgrep uses exit codes similarly to Gitleaks:

| Exit Code | Meaning | `success` | `findings_found` | Runner Behavior |
|-----------|---------|-----------|------------------|-----------------|
| 0 | No findings | True | False | Parse output, persist empty findings |
| 1 | Findings detected | True | True | Parse output, persist findings |
| 2+ | Execution error | False | False | Raise `ProviderError` |

This is handled in `SemgrepResult.success` and `SemgrepResult.findings_found` properties.

## Semgrep Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `semgrep_executable` | `semgrep` | Semgrep executable path |
| `semgrep_timeout_seconds` | `120.0` | Timeout for a single scan |
| `semgrep_config` | `auto` | Rules configuration (uses Semgrep registry) |

## Known Limitations

1. **Severity mapping** — Semgrep severity levels (`ERROR`, `WARNING`, `INFO`) map to `HIGH`, `MEDIUM`, `LOW` respectively. Unknown severities default to `MEDIUM`.
2. **Auto config** — Uses Semgrep registry for rules. Custom `.semgrep.yml` not yet configurable.
3. **Sequential execution** — Trivy runs first, then Gitleaks, then Semgrep. Parallel execution deferred.
4. **No finding deduplication** — Same issue detected across scans creates separate findings.
5. **Source code discarded** — For security, source snippets are not persisted. Future: safe snippet display with proper access controls.

## Deferred Work

- Syft (SBOM generation)
- Grype (vulnerability scanning from SBOM)
- Custom Semgrep rules configuration
- Parallel scanner execution
- Finding deduplication across scans
- Source code snippet display (with proper access controls)
- Per-scanner retry logic
- Background worker infrastructure

## Files Changed

| File | Change |
|------|--------|
| `apps/backend/app/domains/scanners/providers/semgrep/__init__.py` | **Created** |
| `apps/backend/app/domains/scanners/providers/semgrep/runner.py` | **Created** |
| `apps/backend/app/domains/scanners/providers/semgrep/parser.py` | **Created** |
| `apps/backend/app/domains/scanners/providers/semgrep/provider.py` | **Created** |
| `apps/backend/app/domains/scanners/registry.py` | Modified — added Semgrep builder |
| `apps/backend/app/core/config.py` | Modified — added `semgrep_timeout_seconds`, `semgrep_config` |
| `apps/backend/tests/unit/domains/scanners/test_semgrep_parser.py` | **Created** |
| `apps/backend/tests/unit/domains/scanners/test_semgrep_runner.py` | **Created** |
| `apps/backend/tests/unit/domains/scanners/test_semgrep_provider.py` | **Created** |
| `apps/backend/tests/unit/domains/scanners/test_semgrep_multiscanner.py` | **Created** |
| `docs/adr/0013-semgrep-sast.md` | **Created** |
| `docs/sprint-plans/011-sprint-5c3-semgrep-sast.md` | **Created** (this file) |

## Suggested Next Sprint

**Sprint 5C.4 — Syft SBOM + Grype** or **Sprint 6 — Repository Intelligence**.

Syft + Grype are coupled (Grype consumes Syft's SBOM output, requiring a new `SBOMComponent` entity). Repository Intelligence (temporal analysis, trend detection) builds on top of the multi-scanner foundation.
