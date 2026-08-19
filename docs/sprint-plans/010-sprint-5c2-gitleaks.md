# Sprint 5C.2 — Gitleaks Secret Detection

## Objective

Integrate Gitleaks as the second real security scanner behind the existing `ScannerRun` and provider registry architecture, with **mandatory secret redaction** as the primary security requirement.

## What Was Implemented

### 1. Gitleaks Provider (`app/domains/scanners/providers/gitleaks/`)

Four files following the established Trivy pattern:

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `runner.py` | Safe subprocess execution — `create_subprocess_exec` with argument arrays, timeout enforcement, report file cleanup |
| `parser.py` | JSON output parsing with **mandatory secret redaction** — `Match` field (actual secret) discarded during parsing |
| `provider.py` | `AnalysisProvider` adapter — orchestrates acquisition → execution → parsing → persistence → cleanup |

### 2. Scanner Registry Update

- `app/domains/scanners/registry.py` — Gitleaks registered alongside Trivy
- `app/core/config.py` — `gitleaks_timeout_seconds` configuration setting

### 3. Comprehensive Test Suite

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_gitleaks_parser.py` | 18 | Secret redaction (5 tests), severity inference (4), edge cases (8), multiple findings (1) |
| `test_gitleaks_runner.py` | 10 | Exit codes (3), availability (3), path validation (3), subprocess execution (1) |
| `test_gitleaks_provider.py` | 15 | Registration (3), execution lifecycle (8), supports (3), cleanup (1) |
| `test_gitleaks_multiscanner.py` | 9 | Registry (3), configuration parsing (6) |

**Total new tests: 52**

### 4. Documentation

- `docs/adr/0012-gitleaks-secret-detection.md` — Architecture Decision Record
- This sprint report

## Architecture Changes

### Before

```
ANALYSIS_SCANNERS=trivy
    └── ScannerRun(trivy)
            └── TrivyProvider
```

### After

```
ANALYSIS_SCANNERS=trivy,gitleaks
    ├── ScannerRun(trivy)
    │       └── TrivyProvider
    └── ScannerRun(gitleaks)
            └── GitleaksProvider
```

### Scanner Provider Pattern

```
AnalysisOrchestrator
    └── ScannerRun(name="gitleaks")
            └── GitleaksProvider.execute(context)
                    ├── GitHubRepositorySource.acquire()  ← reuse
                    ├── ScannerWorkspace                  ← reuse
                    ├── GitleaksRunner.run_detect()
                    │       └── gitleaks detect --source <path> --report-format json
                    ├── GitleaksResultParser.parse()
                    │       └── Match field DISCARDED (secret redaction)
                    ├── FindingRepository.create()         ← normalized findings
                    └── workspace.cleanup()
```

## Security Guarantees

| Guarantee | Evidence |
|-----------|----------|
| **No secret in database** | Parser discards `Match` field — `test_fake_secret_not_in_any_finding_field` |
| **No secret in API responses** | Findings contain only title, description, location, rule ID |
| **No secret in logs** | Parser `logger.info()` only logs count + run ID |
| **No secret in errors** | Provider errors use safe codes — `test_secret_not_in_error_message` |
| **No secret in frontend** | Findings UI shows rule, file, line — never the detected value |
| **No shell=True** | `create_subprocess_exec` with argument arrays — `test_shell_false` |
| **Report file cleanup** | `finally` block always deletes report — verified in runner tests |
| **Workspace cleanup** | `finally` block always cleans up — `test_workspace_cleanup_on_success/failure` |
| **Timeout enforcement** | `asyncio.wait_for` with configurable timeout — `test_timeout_returns_error` |

## Validation Results

| Check | Result |
|-------|--------|
| Backend ruff format | ✅ 129 files formatted |
| Backend ruff check | ✅ All checks passed |
| Backend pyright | ✅ 0 errors, 0 warnings |
| Backend pytest | ✅ **224 passed** (was 172) |
| Frontend lint | ✅ No issues |
| Frontend vitest | ✅ 72 passed |
| Frontend build | ✅ Success |

### Test Breakdown

| Category | Count |
|----------|-------|
| Scanner tests | 130 |
| Other backend tests | 94 |
| **Total** | **224** |

## Gitleaks Exit Code Semantics

Gitleaks uses exit codes differently than most CLIs:

| Exit Code | Meaning | `success` | `secrets_found` | Runner Behavior |
|-----------|---------|-----------|-----------------|-----------------|
| 0 | No secrets found | True | False | Parse output, persist empty findings |
| 1 | Secrets found | True | True | Parse output, persist findings |
| 2+ | Execution error | False | False | Raise `ProviderError` |

This is handled in `GitleaksResult.success` and `GitleaksResult.secrets_found` properties.

## Known Limitations

1. **Severity heuristic** — Gitleaks doesn't assign severity; the parser infers from rule ID. Unknown rules default to MEDIUM.
2. **No custom rules** — Uses default Gitleaks rules. Custom `.gitleaks.toml` not yet configurable.
3. **Sequential execution** — Trivy runs first, then Gitleaks. Parallel execution deferred.
4. **No secret deduplication** — Same secret detected across scans creates separate findings.

## Deferred Work

- Syft (SBOM generation)
- Grype (vulnerability scanning from SBOM)
- Semgrep (SAST)
- Parallel scanner execution
- Custom Gitleaks rules configuration
- Secret finding deduplication across scans
- Per-scanner retry logic
- Background worker infrastructure

## Files Changed

| File | Change |
|------|--------|
| `apps/backend/app/domains/scanners/providers/gitleaks/__init__.py` | **Created** |
| `apps/backend/app/domains/scanners/providers/gitleaks/runner.py` | **Created** |
| `apps/backend/app/domains/scanners/providers/gitleaks/parser.py` | **Created** |
| `apps/backend/app/domains/scanners/providers/gitleaks/provider.py` | **Created** |
| `apps/backend/app/domains/scanners/registry.py` | Modified — added Gitleaks builder |
| `apps/backend/app/core/config.py` | Modified — added `gitleaks_timeout_seconds` |
| `apps/backend/tests/unit/domains/scanners/test_gitleaks_parser.py` | **Created** |
| `apps/backend/tests/unit/domains/scanners/test_gitleaks_runner.py` | **Created** |
| `apps/backend/tests/unit/domains/scanners/test_gitleaks_provider.py` | **Created** |
| `apps/backend/tests/unit/domains/scanners/test_gitleaks_multiscanner.py` | **Created** |
| `docs/adr/0012-gitleaks-secret-detection.md` | **Created** |
| `docs/sprint-plans/010-sprint-5c2-gitleaks.md` | **Created** (this file) |

## Suggested Next Sprint

**Sprint 5C.3 — Semgrep SAST** or **Sprint 5C.4 — Syft SBOM + Grype**.

Both are natural extensions of the scanner registry. Semgrep is simpler (single scanner, SAST findings map to existing `Finding` model). Syft + Grype are coupled (Grype consumes Syft's SBOM output, requiring a new `SBOMComponent` entity).
