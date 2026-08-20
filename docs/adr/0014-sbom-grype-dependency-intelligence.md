# ADR 0014 — Syft + Grype SBOM & Dependency Intelligence

- **Status:** Accepted
- **Date:** 2026-08-20
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 5C.4 — integrating Syft (SBOM generation) and Grype (vulnerability matching) as the fourth real security scanner

## Context

Sprint 5C.1 established multi-scanner orchestration. Sprint 5C.2 added Gitleaks for secret detection. Sprint 5C.3 added Semgrep for SAST. Sprint 5C.4 adds SBOM-based dependency intelligence using two complementary tools:

- **Syft** — generates a Software Bill of Materials (SBOM) by cataloging all packages and dependencies in a repository
- **Grype** — matches an SBOM against known vulnerability databases to find CVEs

These tools serve different purposes but are closely related: Grype's primary input is an SBOM, which Syft generates. Treating them as a coordinated pipeline (Syft → Grype) rather than independent scanners is the cleanest architectural fit.

### Why Syft + Grype?

| Feature | Syft + Grype | Trivy standalone |
|---------|-------------|------------------|
| SBOM generation | ✅ Full CycloneDX/SPDX | ⚠️ Limited SBOM support |
| Vulnerability matching | ✅ Grype (NVD, GHSA) | ✅ Trivy DB |
| Ecosystem coverage | ✅ 30+ ecosystems | ✅ Broad coverage |
| SBOM interoperability | ✅ CycloneDX (industry standard) | ⚠️ Proprietary |
| Separate SBOM use | ✅ SBOM reusable for compliance | ❌ Tied to Trivy |

**Trade-off:** Trivy also does vulnerability scanning from a lock file, but Syft + Grype provide a more standardized SBOM pipeline that's reusable for compliance and interoperability.

## Decision

### 1. Architecture: Single Provider, Internal Pipeline

Grype is registered as a single `grype` scanner in the registry. Internally, the provider invokes Syft → Grype as a pipeline:

```
GrypeProvider (implements AnalysisProvider)
    ├── GitHubRepositorySource (reuse, no duplication)
    ├── ScannerWorkspace (reuse)
    ├── GrypeRunner
    │   ├── SyftRunner (generates CycloneDX JSON SBOM)
    │   └── GrypeRunner (matches SBOM against vuln DB)
    ├── GrypeResultParser (JSON parsing, safe metadata extraction)
    └── FindingRepository (persist normalized findings)
```

**Rationale:** Syft is an internal implementation detail of the Grype provider. The orchestrator doesn't need to know about Syft — it only sees a `grype` scanner that produces vulnerability findings.

### 2. SBOM Format: CycloneDX JSON

Syft generates a CycloneDX JSON SBOM:

- **CycloneDX** is an OWASP standard — more widely supported than SPDX for vulnerability matching
- **JSON** format — machine-readable, compatible with Grype and other tools
- **Transient** — the SBOM is a temporary file deleted after Grype consumes it

The SBOM is NOT persisted in the database. It's generated, consumed by Grype, and immediately deleted.

### 3. Finding Normalization

Grype vulnerability findings map to the existing `Finding` model:

| Grype field | Finding field |
|-------------|--------------|
| `vulnerability.id` | `vulnerability_id` (CVE-XXXX-XXXX) |
| `artifact.name` | `package_name` |
| `artifact.version` | `installed_version` |
| `fix.versions[0]` | `fixed_version` |
| `vulnerability.severity` | `severity` (mapped to EvoShield enum) |
| `artifact.type` | `location` (ecosystem:package) |
| — | `finding_type` = VULNERABILITY |
| — | `scanner` = "grype" |

### 4. Exit Code Semantics

Both tools use conventional exit codes:

**Syft:**
- Exit 0: SBOM generated successfully

**Grype:**
- Exit 0: No vulnerabilities found
- Exit 1: Vulnerabilities found (NOT a failure)
- Exit 2+: Execution error

### 5. SBOM Lifecycle Security

The SBOM file is treated as sensitive — it contains a complete dependency inventory:

- Created in a secure temporary directory (`tempfile.mkstemp`)
- Deleted in a `finally` block (success, failure, timeout, cancellation)
- Never logged, stored, or returned through the API
- Never included in error messages

### 6. Error Message Sanitization

Provider error messages never include raw stderr from Syft or Grype:

- Syft/Grype stderr may contain repository paths, dependency details, or network errors
- Only safe application-level error codes are used
- The SBOM content is never referenced in exceptions

### 7. Scanner Registry Integration

Grype is registered alongside Trivy, Gitleaks, and Semgrep:

```python
_REGISTRY = {
    "trivy": _build_trivy,
    "gitleaks": _build_gitleaks,
    "semgrep": _build_semgrep,
    "grype": _build_grype,
}
```

Configuration:
```bash
ANALYSIS_SCANNERS=trivy,gitleaks,semgrep,grype
```

### 8. Duplicate Vulnerability Findings

Trivy and Grype may detect the same CVEs. Cross-scanner deduplication is NOT implemented in this sprint — it's documented as a known limitation. Each scanner produces independent findings with `scanner` = "trivy" or "scanner" = "grype" for identification.

## Consequences

### Positive
- Standardized SBOM pipeline (CycloneDX) — reusable for compliance
- Clean separation: Syft generates, Grype consumes
- SBOM is transient — no storage overhead
- Findings normalize into the existing model — no schema changes
- Vulnerability metadata (CVE, package, fix version, ecosystem) preserved
- Error messages sanitized — no raw scanner output leaked
- No migration needed — `FindingType.VULNERABILITY` already exists

### Negative
- Two external binaries required (Syft + Grype) — more installation overhead
- SBOM generation adds scan time (Syft must catalog all packages)
- Cross-scanner deduplication with Trivy not yet implemented (may show duplicate CVEs)
- Grype vulnerability database must be up-to-date for accurate results

### Risks
- Syft or Grype version differences may affect SBOM format or vulnerability matching
- Large repositories may produce very large SBOMs (Syft timeout)
- Network access may be needed for Grype to update its vulnerability database

## Security Measures

| Measure | Implementation |
|---------|---------------|
| SBOM lifecycle | Temporary file, deleted in `finally` block on every code path |
| Error sanitization | Raw stderr never included in exceptions |
| Subprocess safety | `create_subprocess_exec` with argument arrays (no `shell=True`) |
| Path validation | Absolute path required, directory checked |
| Timeout enforcement | `asyncio.wait_for` with configurable timeouts for both Syft and Grype |
| Workspace cleanup | `finally` block always cleans up repository workspace |
| Owner scoping | Findings scoped to analysis run → repository → owner |

## Testing Strategy

- **Parser tests:** Empty findings, single CVE, multiple CVEs, missing fields, severity mapping, ecosystem mapping, fix version extraction
- **Runner tests:** Mocked subprocess — argument construction, no `shell=True`, timeout handling, SBOM cleanup
- **Provider tests:** Registration, execution pipeline, cancellation, workspace cleanup, error handling
- **Multi-scanner tests:** Registry includes all four scanners, configuration parsing
- **No real Syft/Grype required** for unit/integration tests

## Future Work

- Cross-scanner vulnerability deduplication (Trivy + Grype)
- SBOM persistence for compliance use cases
- Grype database update scheduling
- Parallel scanner execution
- Custom Grype vulnerability ignore rules
- SBOM export endpoint for compliance
