/**
 * Repository Intelligence types (Sprint 6).
 *
 * Mirrors the backend RepositoryIntelligence response contract.
 * Provides risk assessment, finding aggregation, risk factors,
 * prioritized findings, trend analysis, and scanner coverage.
 */

export type RiskLevel = "critical" | "high" | "medium" | "low" | "healthy";

export type SeverityCounts = {
  critical: number;
  high: number;
  medium: number;
  low: number;
  unknown: number;
};

export type FindingTypeCounts = {
  vulnerability: number;
  secret: number;
  sast: number;
  license: number;
  configuration: number;
  sbom: number;
};

export type ScannerCounts = {
  trivy: number;
  gitleaks: number;
  semgrep: number;
  grype: number;
};

export type RiskFactor = {
  category: string;
  severity: string;
  count: number;
  message: string;
};

export type PriorityFinding = {
  id: string;
  title: string;
  severity: string;
  finding_type: string;
  scanner: string;
  package_name: string | null;
  vulnerability_id: string | null;
  fixed_version: string | null;
  location: string | null;
  priority_reason: string;
};

export type TrendInfo = {
  has_previous: boolean;
  previous_analysis_id: string | null;
  finding_delta: number | null;
  critical_delta: number | null;
  high_delta: number | null;
  secret_delta: number | null;
  vulnerability_delta: number | null;
  trend: "improving" | "worsening" | "unchanged" | null;
};

export type ScannerDetail = {
  name: string;
  status: string;
  finding_count: number | null;
  duration_ms: number | null;
  failure_reason: string | null;
};

export type ScannerCoverage = {
  total_scanners: number;
  completed_scanners: number;
  failed_scanners: number;
  skipped_scanners: number;
  coverage_percentage: number;
  scanner_details: ScannerDetail[];
};

export type RepositoryIntelligence = {
  repository_id: string;
  analysis_id: string;
  generated_at: string;
  risk_score: number;
  risk_level: RiskLevel;
  analysis_status: string;
  total_findings: number;
  severity_counts: SeverityCounts;
  finding_type_counts: FindingTypeCounts;
  scanner_counts: ScannerCounts;
  risk_factors: RiskFactor[];
  top_findings: PriorityFinding[];
  trend: TrendInfo;
  scanner_coverage: ScannerCoverage;
  summary: string;
};

/** Risk level display metadata. */
export const RISK_LEVEL_META: Record<
  RiskLevel,
  { label: string; color: string; bg: string; border: string }
> = {
  critical: {
    label: "Critical",
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
  },
  high: {
    label: "High",
    color: "text-orange-400",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
  },
  medium: {
    label: "Medium",
    color: "text-yellow-400",
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/30",
  },
  low: {
    label: "Low",
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  healthy: {
    label: "Healthy",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
};

/** Trend display metadata. */
export const TREND_META: Record<
  string,
  { label: string; icon: string; color: string }
> = {
  improving: { label: "Improving", icon: "↓", color: "text-emerald-400" },
  worsening: { label: "Worsening", icon: "↑", color: "text-red-400" },
  unchanged: { label: "Unchanged", icon: "→", color: "text-muted-foreground" },
};
