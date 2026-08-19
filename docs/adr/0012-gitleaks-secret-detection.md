# ADR 0012 — Gitleaks Secret Detection Integration

- **Status:** Accepted
- **Date:** 2026-08-19
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 5C.2 — integrating Gitleaks as the second real security scanner

## Context

Sprint 5C.1 established a multi-scanner orchestration foundation with `ScannerRun` and a provider registry. The registry had only Trivy registered. Sprint 5C.2 adds Gitleaks — a secret detection scanner — as the second real scanner.

Gitleaks is fundamentally different from Trivy:
- **Trivy** scans dependencies and produces vulnerability findings
- **Gitleaks** scans git history and produces **secret findings** with sensitive match values

The critical requirement: Gitleaks may detect real secrets (API keys, tokens, passwords). The system must **never** persist, log, return, or display the actual secret value.

## Decision

### 1. Gitleaks Provider Architecture

Follow the established Trivy pattern exactly:

```
GitleaksProvider (implements AnalysisProvider)
    ├── GitHubRepositorySource (reuse, no duplication)
    ├── ScannerWorkspace (reuse)
    ├── GitleaksRunner (safe subprocess execution)
    ├── GitleaksResultParser (JSON parsing + secret redaction)
    └── FindingRepository (persist normalized findings)
```

**Location:** `app/domains/scanners/providers/gitleaks/`

### 2. Secret Redaction

The parser implements **mandatory secret redaction**:

- The `Match` field from Gitleaks JSON output (containing the actual secret) is **discarded during parsing**
- Only safe metadata is preserved: rule ID, description, file path, line number, commit hash, fingerprint
- Title is constructed from rule ID and file path — never from the match value
- Severity is inferred from rule ID using a heuristic map

**Security invariant:** After parsing, no `ScannerFinding` object contains the detected secret value.

### 3. Exit Code Semantics

Gitleaks uses non-zero exit codes differently than most CLIs:
- **Exit 0:** No secrets found (success)
- **Exit 1:** Secrets found (NOT a failure — findings were detected)
- **Exit 2+:** Execution error (true failure)

The runner exposes `success` and `secrets_found` properties to handle this correctly.

### 4. Report File Handling

Gitleaks writes findings to a `--report-path` file. The runner:
1. Creates a temporary report file via `tempfile.mkstemp`
2. After execution, reads stdout first, falls back to report file if stdout is empty
3. **Always deletes the report file** in a `finally` block — even on failure or cancellation
4. Report files may contain secrets and must never persist

### 5. Error Message Sanitization

Provider error messages never include raw `stderr` from Gitleaks. Scanner stderr may contain:
- Discovered secret values
- Sensitive repository paths
- Internal scanner details

All errors use safe application-level codes:
- `scanner_unavailable` — Gitleaks not installed
- `scanner_execution_failed` — non-zero exit code
- `repository_too_large` — size limit exceeded
- `github_not_connected` — no GitHub credentials

### 6. Scanner Registry Integration

Gitleaks is registered alongside Trivy:

```python
_REGISTRY = {
    "trivy": _build_trivy,
    "gitleaks": _build_gitleaks,
}
```

Configuration:
```bash
ANALYSIS_SCANNERS=trivy,gitleaks
```

## Consequences

### Positive
- Secret values never enter the database, API responses, frontend, logs, or error messages
- Gitleaks follows the established scanner pattern — no new abstractions needed
- Exit-code semantics handled correctly (exit 1 = findings, not failure)
- Report files always cleaned up, even on failure
- Error messages sanitized — no raw scanner output leaked

### Negative
- Severity inference from rule ID is a heuristic — may not match organizational risk levels
- Gitleaks exit-code-1-as-success may surprise developers unfamiliar with the tool

### Risks
- Report file in temp directory could theoretically be read by another process between creation and deletion (low risk — OS temp directory, short lifetime)
- Custom Gitleaks rules may not map to expected severity levels

## Security Measures

| Measure | Implementation |
|---------|---------------|
| Secret redaction | `Match` field discarded during parsing |
| Error sanitization | Raw `stderr` never included in exceptions |
| Report cleanup | `finally` block always deletes report file |
| Subprocess safety | `create_subprocess_exec` with argument arrays (no `shell=True`) |
| Path validation | Absolute path required, directory checked |
| Timeout enforcement | `asyncio.wait_for` with configurable timeout |
| Workspace cleanup | `finally` block always cleans up workspace |

## Testing Strategy

- **Secret redaction tests:** Fake Gitleaks JSON with `SUPER_SECRET_TEST_VALUE` — verify the value never appears in any normalized finding field
- **Error message tests:** Verify `SUPER_SECRET_TEST_VALUE` never appears in `ProviderError` messages
- **Runner tests:** Mocked subprocess — verify argument construction, no `shell=True`, timeout handling
- **Parser tests:** Empty input, malformed JSON, missing fields, dict-wrapped output, None input
- **Multi-scanner tests:** Registry includes both `trivy` and `gitleaks`, configuration parsing
- **No real Gitleaks required** for unit/integration tests

## Future Work

- Per-rule severity configuration
- Custom Gitleaks rule sets
- Secret finding deduplication across scans
- Gitleaks allowlist integration
- Parallel scanner execution
