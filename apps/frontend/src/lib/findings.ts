/**
 * Finding domain types (Sprint 5A).
 *
 * Mirrors the backend Finding contract.  Findings are the normalized
 * security scan results produced by any scanner (Trivy today, more later).
 */

export type Severity = "unknown" | "low" | "medium" | "high" | "critical";

export type FindingType =
  | "vulnerability"
  | "secret"
  | "sast"
  | "license"
  | "configuration"
  | "sbom";

/** Wire shape of one finding from the backend. */
export type Finding = {
  id: string;
  analysis_run_id: string;
  scanner: string;
  scanner_version: string;
  finding_type: FindingType;
  severity: Severity;
  title: string;
  description: string | null;
  package_name: string | null;
  installed_version: string | null;
  fixed_version: string | null;
  vulnerability_id: string | null;
  references: string[];
  location: string | null;
  created_at: string | null;
};

/** Paginated findings response. */
export type FindingPage = {
  items: Finding[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

/** Severity display metadata. */
export type SeverityMeta = {
  label: string;
  color: string;
  bg: string;
  border: string;
};

export const SEVERITY_META: Record<Severity, SeverityMeta> = {
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
  unknown: {
    label: "Unknown",
    color: "text-zinc-400",
    bg: "bg-zinc-500/10",
    border: "border-zinc-500/30",
  },
};

export const FINDING_TYPE_META: Record<FindingType, { label: string }> = {
  vulnerability: { label: "Vulnerability" },
  secret: { label: "Secret" },
  sast: { label: "SAST" },
  license: { label: "License" },
  configuration: { label: "Configuration" },
  sbom: { label: "SBOM" },
};

/** Severity sort priority (critical > high > medium > low > unknown). */
export const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  unknown: 4,
};
