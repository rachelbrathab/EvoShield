# Sprint 5C.4 — SBOM + Grype Dependency Intelligence

- **Date:** 2026-08-20
- **Duration:** Single session
- **Status:** ✅ Complete

## Goal

Integrate Syft (SBOM generation) and Grype (vulnerability matching) as the fourth security scanner, providing SBOM-based dependency intelligence alongside Trivy, Gitleaks, and Semgrep.

## Architecture

```
AnalysisRun
    ├── ScannerRun(trivy)     ← Sprint 5A/5B
    ├── ScannerRun(gitleaks)  ← Sprint 5C.2
    ├── ScannerRun(semgrep)   ← Sprint 5C.3
    └── ScannerRun(grype)     ← NEW
            └── GrypeProvider
                    ├── GitHubRepositorySource (reuse)
                    ├── GrypeRunner
                    │   ├── Syft (CycloneDX SBOM generation)
                    │   └── Grype (vulnerability matching)
                    ├── GrypeResultParser (safe metadata extraction)
                    └── FindingRepository
```

## Key Decisions

1. **Single provider, internal pipeline** — Syft is an internal implementation detail of the Grype provider. The orchestrator only sees `grype`.
2. **CycloneDX JSON** — industry-standard SBOM format, compatible with Grype and other tools.
3. **Transient SBOM** — generated, consumed, immediately deleted. Never persisted.
4. **No migration needed** — `FindingType.VULNERABILITY` already exists.

## Files Created/Modified

| File | Change |
|------|--------|
| `app/domains/scanners/providers/grype/__init__.py` | **Created** — package init |
| `app/domains/scanners/providers/grype/runner.py` | **Created** — Syft + Grype safe subprocess execution |
| `app/domains/scanners/providers/grype/parser.py` | **Created** — Grype JSON → normalized findings |
| `app/domains/scanners/providers/grype/provider.py` | **Created** — AnalysisProvider adapter |
| `app/domains/scanners/registry.py` | Modified — Grype registered |
| `app/core/config.py` | Modified — `syft_executable`, `grype_executable`, timeouts |
| `tests/unit/domains/scanners/test_grype_runner.py` | **Created** — 14 tests |
| `tests/unit/domains/scanners/test_grype_parser.py` | **Created** — 23 tests |
| `tests/unit/domains/scanners/test_grype_provider.py` | **Created** — 14 tests |
| `tests/unit/domains/scanners/test_grype_multiscanner.py` | **Created** — 10 tests |
| `docs/adr/0014-sbom-grype-dependency-intelligence.md` | **Created** |
| `docs/sprint-plans/012-sprint-5c4-sbom-grype.md` | **Created** |
| `README.md` | Modified — sprint roadmap |
| `docs/backend-structure.md` | Modified — Grype provider layout |

## Validation

| Check | Result |
|---|---|
| Backend ruff format | ✅ 145 files |
| Backend ruff check | ✅ All passed |
| Backend pyright | ✅ 0 errors, 0 warnings |
| Backend pytest (SQLite) | ✅ **360 passed** (was 289) |
| Frontend lint | ✅ Clean |
| Frontend vitest | ✅ **72 passed** |
| Frontend build | ✅ Success |

## Test Breakdown

| Test file | Tests |
|-----------|-------|
| test_grype_runner.py | 14 (command construction, timeout, missing exec, cleanup) |
| test_grype_parser.py | 23 (empty, single, multiple, missing fields, severity, ecosystem) |
| test_grype_provider.py | 14 (registration, execution, cancellation, cleanup, error handling) |
| test_grype_multiscanner.py | 10 (all 4 scanners registered, config parsing) |
| **Total new** | **61** |

## Security Audit

- ✅ No `shell=True` in implementation code
- ✅ SBOM temporary file deleted in `finally` block on every code path
- ✅ Raw stderr from Syft/Grype never included in error messages
- ✅ No raw scanner output persisted or returned through API
- ✅ `create_subprocess_exec` with explicit argument arrays
- ✅ Path validation (absolute, exists, is directory)
- ✅ Timeout enforcement via `asyncio.wait_for`

## Known Limitations

1. **No cross-scanner deduplication** — Trivy and Grype may detect the same CVE. Each produces independent findings with `scanner` identification.
2. **Syft/Grype not installed locally** — tests use mocked execution. Real validation requires installing both tools.
3. **Grype database freshness** — vulnerability matching accuracy depends on the local Grype database being up-to-date.
4. **No SBOM persistence** — the SBOM is transient. Future compliance use cases may require storing it.

## Scanner Ecosystem (Complete)

```
trivy    → dependency/vulnerability scanning
gitleaks → secret detection
semgrep  → SAST (source-code security patterns)
grype    → SBOM-based vulnerability intelligence (Syft → Grype)
```

All four scanners use the same architecture:
- ScannerRun lifecycle tracking
- Provider registry plug-in
- FindingRepository for persistence
- GitHubRepositorySource for acquisition
- Safe subprocess execution (no shell=True)

**Sprint 5C.4 is done. Awaiting approval before Sprint 6 (Repository Intelligence).**
