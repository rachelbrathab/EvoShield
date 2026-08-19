# ADR 0011 — Multi-Scanner Orchestration Architecture

- **Status:** Accepted
- **Date:** 2026-08-19
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 5C.1 — refactoring single-scanner pipeline into multi-scanner orchestration

## Context

Sprint 5A/5B built a complete analysis pipeline with a single scanner (Trivy). The architecture used a 1:1 relationship between `AnalysisRun` and `AnalysisProvider`. This worked for a single scanner but couldn't support multiple independent scanners (Trivy, Gitleaks, Semgrep, Syft, Grype) without either:

1. Modifying the orchestrator for each new scanner
2. Creating separate analysis runs per scanner
3. Coupling all scanner logic into one monolithic provider

## Decision

### 1. ScannerRun Entity

Introduce `ScannerRun` — a child entity of `AnalysisRun`:

```
AnalysisRun  1 ──▶ * ScannerRun
```

Each `ScannerRun` tracks one scanner's execution independently with its own lifecycle, timing, and outcome.

**Location:** `app/models/scanner_run.py`

### 2. Scanner Registry

Replace the single-provider factory with a registry pattern:

```python
# app/domains/scanners/registry.py
_REGISTRY: dict[str, BuilderFactory] = {
    "trivy": _build_trivy,
}
```

Adding a new scanner = implementing the provider + registering it. No orchestrator changes.

### 3. Dual-Mode Orchestrator

The orchestrator supports two modes:

1. **Single-provider** (backward compatible): `provider` is set, `scanner_providers` is `None`
2. **Multi-scanner**: `scanner_providers` is a list of providers

The multi-scanner path creates a `ScannerRun` per configured scanner and executes them sequentially.

### 4. Configuration

```bash
# Single provider (backward compatible)
ANALYSIS_PROVIDER=trivy

# Multi-scanner (overrides ANALYSIS_PROVIDER when set)
ANALYSIS_SCANNERS=trivy,gitleaks,semgrep
```

### 5. ScannerRun Lifecycle

```
ScannerRun: PENDING → RUNNING → COMPLETED
                            → FAILED
                            → CANCELLED
                            → SKIPPED
```

Transitions are validated at the application level. The partial unique index enforces at most one active run per scanner per analysis.

## Consequences

### Positive
- Adding a new scanner requires only: implement provider + register in `_REGISTRY`
- No changes to orchestrator, API, or database for new scanners
- Independent failure isolation — one scanner failing doesn't block others
- Independent timing and finding counts per scanner
- Backward compatible — `ANALYSIS_PROVIDER=trivy` still works

### Negative
- Adds `scanner_runs` table and `ScannerRunRepository`
- Slightly more complex orchestrator logic
- Sequential execution (not parallel) — acceptable for Sprint 5C.1

### Risks
- Partial unique index not in ORM model (only in migration) — enforced at application level
- Scanner-specific execution contexts may diverge over time

## Future Work
- Parallel scanner execution
- Dependency-aware execution (Syft → Grype)
- Scanner-specific findings metadata
- Per-scanner retry logic
- Scanner health checks
