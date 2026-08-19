# ADR 0009 — Security Scanner Architecture

- **Status:** Accepted
- **Date:** 2026-08-19
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 5A — first real scanner (Trivy) integration

## Context

EvoShield's analysis infrastructure (Sprint 4A) provides an `AnalysisProvider`
port and an `AnalysisOrchestrator` state machine, but the only provider is a
fake simulation.  Sprint 5A adds the first real scanner — Trivy — and the
supporting infrastructure (normalized findings, database persistence, API
endpoints, frontend display) that every future scanner will reuse.

## Decision

### 1. Scanner abstraction in `domains/scanners/`

Scanner-specific logic lives in `app/domains/scanners/`, not in the analysis
orchestrator.  The dependency rule: scanners consume analysis artifacts and
produce findings — they never import sibling domains.

```
domains/scanners/
├── enums.py          Severity, FindingType enums
├── ports.py          ScannerProvider protocol, ScannerFinding dataclass
├── repository.py     FindingRepository (data access)
└── providers/
    └── trivy/
        ├── __init__.py
        ├── provider.py    TrivyProvider (AnalysisProvider adapter)
        ├── runner.py       Safe subprocess execution
        └── parser.py       Trivy JSON → ScannerFinding normalization
```

### 2. Trivy isolation

All Trivy-specific code is behind `providers/trivy/`.  The orchestrator,
API layer, and frontend never see Trivy details.  Adding Syft, Grype,
Semgrep, or Gitleaks later means adding a new adapter under `providers/`
and registering it in `factory.py`.

### 3. Subprocess safety

The Trivy runner uses `asyncio.create_subprocess_exec()` with explicit
argument arrays — never `shell=True`.  Repository paths are validated
(absolute, exists, is directory) before execution.  No user-controlled
strings reach shell interpretation.

### 4. Normalized findings

Every scanner maps its native output to `ScannerFinding` objects with
universal fields: severity, finding_type, title, description, package info,
vulnerability ID, references, location.  The `findings` table stores these
normalized fields — no scanner-specific columns.  Raw output is optionally
stored for debugging but never as the primary data model.

### 5. Finding types and severities

Enums use the same VARCHAR pattern as `AnalysisStatus`: `native_enum=False`,
`create_constraint=False`, `validate_strings=True`.  New values are code-only
additions — no migration required.

### 6. Temporary workspace

Scanner execution uses `ScannerWorkspace` (a `tempfile.TemporaryDirectory`
context manager) for clean lifecycle management.  All temporary files are
cleaned up even when scanning fails.

### 7. Provider selection

`ANALYSIS_PROVIDER` in settings selects the adapter:
- `"fake"` — simulation (default for dev/testing)
- `"trivy"` — real vulnerability scanning

Adding a new scanner is one settings value + one adapter class.

## Consequences

### Positive
- Clean separation: scanners are adapters, not core logic
- Subprocess safety: no shell injection possible
- Extensible: new scanners are plug-and-play
- Testable: mocked Trivy tests in CI, no real binary needed
- Normalized: findings are scanner-agnostic

### Negative
- One layer of indirection between scanner output and stored findings
- Trivy's JSON format may change between versions (mitigated by parser)
- Temporary workspace adds I/O overhead (acceptable for security scanning)

### Risks
- Trivy may not be installed in all dev environments → handled by
  `scanner_unavailable` error code and clear installation docs
- Large repositories may take a long time to scan → mitigated by
  configurable timeout

## References

- `docs/adr/0008-analysis-domain.md` — analysis orchestration layer
- `app/domains/scanners/` — scanner domain implementation
- `app/domains/scanners/providers/trivy/` — Trivy adapter
- `app/models/finding.py` — findings ORM model
- `alembic/versions/20260806_0006_findings.py` — findings migration
