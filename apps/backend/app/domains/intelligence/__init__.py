"""Repository Intelligence domain — aggregates scanner evidence into actionable insight.

This domain answers: "How secure is this repository?"

It consumes evidence from the scanner layer (Trivy, Gitleaks, Semgrep, Grype)
and produces deterministic, explainable repository intelligence:

- Finding aggregation (by severity, type, scanner)
- Risk scoring (transparent engineering heuristic, NOT a validated security standard)
- Risk factors (categorized explanations)
- Finding prioritization (what to fix first)
- Conservative deduplication (same CVE/package grouping)
- Trend analysis (improving / worsening / unchanged)
- Scanner coverage (which scanners succeeded/failed)

All computation is deterministic, bounded, and testable.
No LLM, no machine learning, no external services.
"""
