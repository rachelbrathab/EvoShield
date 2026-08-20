# ADR 0013 — Semgrep SAST Integration

- **Status:** Accepted
- **Date:** 2026-08-19
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 5C.3 — integrating Semgrep as the third real security scanner

## Context

Sprint 5C.1 established a multi-scanner orchestration foundation. Sprint 5C.2 added Gitleaks for secret detection. Sprint 5C.3 adds Semgrep — a static application security testing (SAST) scanner — as the third real scanner.

Semgrep is fundamentally different from Trivy and Gitleaks:
- **Trivy** scans dependencies and produces vulnerability findings
- **Gitleaks** scans git history and produces secret findings
- **Semgrep** scans source code and produces **SAST/code pattern findings** with CWE/OWASP metadata

Semgrep produces source-code-level security findings (injection flaws, hardcoded credentials, insecure configurations, etc.) by analyzing source code patterns rather than known vulnerabilities or secrets.

## Decision

### 1. Semgrep Provider Architecture

Follow the established Trivy/Gitleaks pattern exactly:

```
SemgrepProvider (implements AnalysisProvider)
    ├── GitHubRepositorySource (reuse, no duplication)
    ├── ScannerWorkspace (reuse)
    ├── SemgrepRunner (safe subprocess execution)
    ├── SemgrepResultParser (JSON parsing + source code safety)
    └── FindingRepository (persist normalized findings)
```

**Location:** `app/domains/scanners/providers/semgrep/`

### 2. Source Code Safety

Semgrep output can contain source-code snippets (via `extra.lines`, `extra.lines_of_code`, metavariables). The parser implements **mandatory source code safety**:

- Only the `message` field is extracted from `extra` — not `lines`, `lines_of_code`, `metavars`, or `fixes`
- Source-code snippets are never persisted to the database
- Source-code snippets are never returned in API responses
- Source-code snippets are never displayed in the frontend

**Security invariant:** After parsing, no `ScannerFinding` object contains source code from the scanned repository.

### 3. Exit Code Semantics

Semgrep uses exit codes similarly to Gitleaks:
- **Exit 0:** No findings (clean scan)
- **Exit 1:** Findings detected (NOT a failure)
- **Exit 2+:** Execution error (true failure)

The runner exposes `success` and `findings_found` properties to handle this correctly.

### 4. Rules Configuration

Semgrep is configured with `--config auto` by default, which uses the Semgrep registry for security rules. This provides:
- Deterministic, maintainable rule set
- Regular updates from the Semgrep community
- Coverage of common vulnerability patterns (CWE, OWASP)

Future: Custom rule sets can be added via `SEMGREP_CONFIG` configuration.

### 5. Error Message Sanitization

Provider error messages never include raw `stderr` from Semgrep. Scanner stderr may contain:
- Source code snippets from the scanned repository
- Internal scanner details
- Repository paths

All errors use safe application-level codes:
- `scanner_unavailable` — Semgrep not installed
- `scanner_execution_failed` — non-zero exit code
- `repository_too_large` — size limit exceeded
- `github_not_connected` — no GitHub credentials

### 6. Scanner Registry Integration

Semgrep is registered alongside Trivy and Gitleaks:

```python
_REGISTRY = {
    "trivy": _build_trivy,
    "gitleaks": _build_gitleaks,
    "semgrep": _build_semgrep,
}
```

Configuration:
```bash
ANALYSIS_SCANNERS=trivy,gitleaks,semgrep
```

## Consequences

### Positive
- Source code snippets never enter the database, API responses, frontend, logs, or error messages
- Semgrep follows the established scanner pattern — no new abstractions needed
- CWE/OWASP metadata is preserved for rich finding context
- Exit-code semantics handled correctly (exit 1 = findings, not failure)
- Error messages sanitized — no raw scanner output leaked
- Security rules maintained by Semgrep community — low maintenance burden

### Negative
- Severity mapping from Semgrep to EvoShield is a lossy transformation (Semgrep's severity levels don't map 1:1)
- `auto` config may produce different findings across Semgrep versions (rules can change)
- Source code snippets are discarded — some context may be lost for developers

### Risks
- Semgrep's `auto` config may include rules that are not security-relevant (noise)
- Large repositories may produce thousands of findings (filtering needed in future)
- Semgrep version differences may affect rule evaluation

## Security Measures

| Measure | Implementation |
|---------|---------------|
| Source code safety | `extra.lines`, `metavars`, `fixes` discarded during parsing |
| Error sanitization | Raw `stderr` never included in exceptions |
| Subprocess safety | `create_subprocess_exec` with argument arrays (no `shell=True`) |
| Path validation | Absolute path required, directory checked |
| Timeout enforcement | `asyncio.wait_for` with configurable timeout |
| Workspace cleanup | `finally` block always cleans up workspace |

## Testing Strategy

- **Source code safety tests:** Fake Semgrep JSON with `VERY_SENSITIVE_TEST_SOURCE_CODE` — verify the value never appears in any normalized finding field
- **Error message tests:** Verify `VERY_SENSITIVE_TEST_SOURCE_CODE` never appears in `ProviderError` messages
- **Runner tests:** Mocked subprocess — verify argument construction, no `shell=True`, timeout handling
- **Parser tests:** Empty input, malformed JSON, missing fields, severity mapping, CWE/OWASP extraction
- **Multi-scanner tests:** Registry includes all three scanners, configuration parsing
- **No real Semgrep required** for unit/integration tests

## Future Work

- Custom rule set configuration (project-owned `.semgrep.yml`)
- Finding deduplication across scans
- Severity override configuration
- Parallel scanner execution
- Semgrep ignore file support (`.semgrepignore`)
- Finding grouping by rule ID
