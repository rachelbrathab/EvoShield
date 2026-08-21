# ADR 0015 — Repository Intelligence

- **Status:** Accepted
- **Date:** 2026-08-20
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 6 — turning scanner evidence into repository intelligence

## Context

Sprints 5A-5C.4 built four security scanners (Trivy, Gitleaks, Semgrep, Grype) that produce normalized findings. Sprint 6 aggregates this evidence into actionable repository intelligence — answering "How secure is this repository?"

The key challenge: raw finding counts are not intelligence. The system must produce meaningful, explainable, deterministic insights that help developers prioritize remediation.

## Decision

### 1. Architecture: Dedicated Intelligence Domain

Create `app/domains/intelligence/` — a bounded context separate from scanners and analysis:

```
app/domains/intelligence/
├── __init__.py      — domain documentation
├── scoring.py       — deterministic risk scoring engine
├── schemas.py       — API response contracts (Pydantic models)
└── service.py       — intelligence computation service
```

**Rationale:** Intelligence consumes evidence from scanners but has different responsibilities (aggregation, scoring, prioritization, trends). Keeping it separate follows the Single Responsibility Principle and avoids polluting scanner internals.

### 2. Persistence: Dynamic Computation (No New Tables)

All intelligence is computed dynamically from existing data:
- `Finding` table → severity/type/scanner aggregation
- `AnalysisRun` table → trend comparison
- `ScannerRun` table → scanner coverage

**No new database tables are created.** The intelligence response is generated on-the-fly per request. This is acceptable because:
- Findings per analysis are small (typically < 1000)
- Computation is CPU-bound, not I/O-bound
- No expensive queries (simple GROUP BY + counts)
- Caching can be added later if needed

### 3. Risk Scoring: Transparent Engineering Heuristic

**IMPORTANT: This is NOT a validated security standard.** It is a deterministic, explainable engineering heuristic.

**Formula:**
```
base_score = 100
severity_impact = Σ(weight[severity] × count)
secret_penalty = 20 if secrets > 0 else 0
unfixed_penalty = 5 × unfixed_vuln_count
risk_score = clamp(base_score - severity_impact - secret_penalty - unfixed_penalty, 0, 100)
```

**Severity weights:**
| Severity | Weight | Rationale |
|----------|--------|-----------|
| Critical | 25 | Immediate action required |
| High | 15 | Urgent attention needed |
| Medium | 8 | Should be addressed |
| Low | 2 | Minor, monitor |
| Unknown | 1 | Conservative default |

**Risk levels:**
| Score Range | Level | Description |
|-------------|-------|-------------|
| 0-20 | critical | Immediate action required |
| 21-40 | high | Urgent attention needed |
| 41-60 | medium | Should be addressed |
| 61-80 | low | Minor issues, monitor |
| 81-100 | healthy | Good security posture |

### 4. Risk Factors

Beyond the score, the system generates categorized risk factors:

```json
{
  "category": "secrets",
  "severity": "critical",
  "count": 2,
  "message": "2 potential secrets detected. Investigate immediately."
}
```

Each factor provides a human-readable explanation, making the intelligence actionable.

### 5. Finding Prioritization

Findings are ranked for developer attention by:
1. **Severity** (critical > high > medium > low > unknown)
2. **Fix availability** (vulnerabilities with fixes first)
3. **Finding type** (secrets > vulnerabilities > SAST)

Each prioritized finding includes a `priority_reason` explaining why it matters.

### 6. Trend Analysis

Compare current analysis with the most recent completed analysis:
- `finding_delta`: total finding change
- `critical_delta`: critical finding change
- `high_delta`: high finding change
- `secret_delta`: secret finding change
- `vulnerability_delta`: vulnerability finding change
- `trend`: "improving" / "worsening" / "unchanged"

Only completed analyses are compared — failed/incomplete runs are excluded.

### 7. Scanner Coverage

Report which scanners succeeded/failed:
```json
{
  "total_scanners": 4,
  "completed_scanners": 3,
  "failed_scanners": 1,
  "coverage_percentage": 75.0,
  "scanner_details": [...]
}
```

Zero findings with 0% scanner coverage is NOT healthy — the system distinguishes "no findings" from "analysis failed."

### 8. Conservative Deduplication

Cross-scanner deduplication is NOT implemented in this sprint. If Trivy and Grype detect the same CVE, both findings are preserved with scanner provenance. Deduplication is documented as a known limitation and future work.

### 9. API Design

Single endpoint: `GET /analysis/{id}/intelligence`

Owner-scoped through the existing chain: intelligence → analysis_run → repository → owner.

### 10. Frontend

Intelligence is displayed on the analysis detail page as a new section above findings:
- Risk score + level badge
- Severity count cards (critical/high/medium/low)
- Risk factors with explanations
- Priority findings (what to fix first)
- Scanner coverage
- Trend indicator (improving/worsening/unchanged)
- Summary

## Consequences

### Positive
- Deterministic, explainable risk scoring — no black-box AI
- Dynamic computation — no database schema changes
- Clean separation from scanner internals
- Actionable intelligence (risk factors + prioritization)
- Trend tracking across analyses
- Scanner coverage distinguishes "no findings" from "analysis failed"

### Negative
- Risk score is a heuristic, not a validated security metric
- Cross-scanner deduplication not yet implemented
- No persistence — intelligence is recomputed per request
- Trend limited to the most recent completed analysis

### Risks
- Risk weights may not perfectly reflect actual security impact
- Large numbers of findings could make the score floor at 0 quickly
- Trend analysis requires at least two completed analyses

## Security Measures

| Measure | Implementation |
|---------|---------------|
| Owner scoping | Intelligence queries join through analysis_run → repository → owner |
| No raw scanner output | Intelligence never exposes raw findings or scanner data |
| No secrets | Secret values are never included in risk factors or summaries |
| No source code | Source code snippets are never included |
| No logging of findings | Intelligence service has no logger calls |
| Deterministic | Same inputs always produce the same output |

## Testing Strategy

- **Scoring tests:** Bounds, weights, determinism, risk levels, aggregation helpers
- **Service tests:** Ownership enforcement, aggregation, risk factors, prioritization, trend, coverage, summary
- **API tests:** Endpoint authentication, ownership, response shape
- **Property tests:** risk_score ∈ [0, 100], more severe findings worsen score, failed analysis not healthier than valid
