# Research Notes

Living research log for EvoShield decisions. Each entry records the question,
what was considered, and what was chosen — so the reasoning is reproducible.

## 2026-08-03 — Scanner selection & orchestration approach

**Question:** Which tools should power the supply chain scanning layer?

**Considered:**

- **Trivy** (Aqua Security): container/image, filesystem and repo scanning;
  huge CVE database, actively maintained. Industry default for CI.
- **Syft** (Anchore): SBOM generation from containers, filesystems and package
  managers; produces CycloneDX/Syft formats. Natural partner to Grype.
- **Grype** (Anchore): vulnerability matching against multiple feeds; pairs
  directly with Syft SBOMs.
- **Semgrep** (Semgrep Inc.): pattern-based static analysis; excellent for
  custom rules, IaC and secrets-adjacent code patterns. OSS core available.
- **Gitleaks**: purpose-built secret scanning, `pre-commit` friendly, low
  false-positive rate.

**Choice:** Use all five, each for its strength:

- Syft → SBOM (feeds inventory + temporal tracking)
- Trivy + Grype → vulnerabilities (cross-checked for coverage)
- Gitleaks → secrets
- Semgrep → risky code / IaC patterns

**Orchestration note:** scanners run as pinned CLI binaries executed by the
backend (subprocess or containerized later); findings are normalized into a
unified `Finding` model rather than stored per-tool. This keeps the prediction
layer tool-agnostic (Sprint 7).

## 2026-08-03 — Prediction approach (early)

**Question:** How should "future repository risk" be estimated?

**Direction:** Feature-engineered time series per repository:

- Temporal features: finding density over time, dependency churn, release
  cadence, secret exposure trend, language/ecosystem mix, CVSS-weighted
  vulnerability curve.
- Model: gradient boosting (XGBoost/HistGradientBoosting) or linear regression
  with strong baselines (persistence/rolling mean) — evaluated with time-series
  cross-validation (no leakage).
- Output: 90-day risk score (0–100) + confidence interval + feature attribution.

Deferred to Sprint 7; research note exists so feature engineering aligns with
the data model built in Sprints 3–6.
