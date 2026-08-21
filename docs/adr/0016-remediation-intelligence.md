# ADR 0016: Remediation Intelligence

## Status

Accepted — Sprint 7

## Context

EvoShield's scanner ecosystem (Trivy, Gitleaks, Semgrep, Grype) produces
normalized findings, and Sprint 6's IntelligenceService aggregates these into
repository-level intelligence (risk score, severity counts, trend). However,
the system lacked:

1. **Finding lifecycle** — no way to track whether a finding was investigated,
   resolved, or marked as a false positive.
2. **Remediation guidance** — no actionable explanation of what to do about
   each finding.
3. **Fix availability** — no normalized concept of whether a fix exists.
4. **Remediation progress** — no way to measure how much has been addressed.

Sprint 7 adds a deterministic remediation intelligence layer on top of the
existing Finding model without modifying scanner internals.

## Decision

### FindingStatus is a separate table

The `Finding` model is immutable scanner-produced data. Adding a mutable
lifecycle status directly to `Finding` would mix concerns: immutable scan
results with mutable user actions. Instead, a separate `finding_statuses`
table tracks user-initiated status changes.

- Default state: OPEN (no row means OPEN)
- Transitions: OPEN → ACKNOWLEDGED → RESOLVED / FALSE_POSITIVE
- Each row records who set the status and when
- One row per finding (enforced by unique constraint)

### Guidance is deterministic and rule-based

Remediation guidance is computed from normalized Finding fields using
deterministic rules:

- **Secrets**: Revoke, rotate, remove from history, use secret management
- **Vulnerabilities**: Upgrade to fixed version, verify no regressions
- **SAST**: Review flagged code, apply secure pattern
- **License**: Review terms, consider alternatives
- **Configuration**: Review and harden settings
- **Unknown**: Generic guidance, consult scanner documentation

No LLM, no ML, no prediction. All guidance is deterministic, bounded,
and testable.

### Fix availability is normalized

`FixAvailability` enum captures whether a known fix exists:

- `fix_available` — a fixed version is known
- `no_known_fix` — the vulnerability has no patched version
- `not_applicable` — secrets don't have "fix versions"
- `unknown` — insufficient information to determine

### Priority is a composite score

Finding priority is computed as a weighted composite:

```
priority = status_weight * 1000 + severity_weight * 100 + fix_weight * 10 + type_weight
```

Lower number = higher priority. Status dominates (OPEN > ACKNOWLEDGED > RESOLVED > FALSE_POSITIVE),
then severity, fix availability, and finding type.

### Intelligence includes remediation metrics

The `RepositoryIntelligence` response now includes `RemediationMetrics`:

- open / acknowledged / resolved / false_positive counts
- fixable count
- remediation rate (percentage resolved or false positive)

### Remediation API endpoints

Three owner-scoped endpoints:

1. `GET /analysis/{id}/remediation` — full remediation intelligence
2. `GET /analysis/{id}/findings/{fid}/remediation` — single finding details
3. `PATCH /analysis/{id}/findings/{fid}/status` — update status

All endpoints enforce owner scoping through the
finding → analysis_run → repository → owner chain.

## Consequences

- The Finding model remains immutable — no schema changes required for status
- Historical remediation is tracked through status records with timestamps
- The intelligence service includes remediation metrics in its response
- The frontend shows a remediation plan with actionable guidance
- Cross-user access is enforced at the API boundary
- No raw scanner output, secrets, or source code leak through remediation

## Testing

- 31 remediation-specific tests covering guidance, status, prioritization, API
- Secret sentinel tests verify no sensitive data leaks through remediation
- All 438 backend tests pass
- Frontend lint, tests, and build pass

## Known Limitations

1. No cross-analysis correlation — findings are remediation-tracked per analysis
2. No automatic resolution — status changes are user-initiated only
3. No notification system for status changes
4. PostgreSQL not validated locally (CI only)
