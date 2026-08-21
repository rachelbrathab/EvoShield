/**
 * Remediation Intelligence types (Sprint 7).
 *
 * Mirrors the backend remediation response contracts.
 * Provides finding lifecycle, remediation guidance, fix availability,
 * and remediation metrics.
 */

export type RemediationStatus =
  | "open"
  | "acknowledged"
  | "resolved"
  | "false_positive";

export type FixAvailability =
  | "fix_available"
  | "no_known_fix"
  | "not_applicable"
  | "unknown";

export type RemediationGuidance = {
  summary: string;
  recommendation: string;
  steps: string[];
};

export type FindingRemediation = {
  finding_id: string;
  severity: string;
  finding_type: string;
  scanner: string;
  title: string;
  status: RemediationStatus;
  priority: number;
  fix_availability: FixAvailability;
  package_name: string | null;
  installed_version: string | null;
  fixed_version: string | null;
  vulnerability_id: string | null;
  location: string | null;
  guidance: RemediationGuidance;
};

export type RemediationSummary = {
  total_findings: number;
  open_count: number;
  acknowledged_count: number;
  resolved_count: number;
  false_positive_count: number;
  fixable_count: number;
  unfixable_count: number;
  remediation_rate: number;
  critical_open: number;
  high_open: number;
};

export type AnalysisRemediation = {
  analysis_id: string;
  repository_id: string;
  summary: RemediationSummary;
  findings: FindingRemediation[];
};

export type RemediationStatusUpdate = {
  status: RemediationStatus;
  note?: string;
};

/** Status display metadata. */
export const STATUS_META: Record<
  RemediationStatus,
  { label: string; color: string; bg: string; border: string }
> = {
  open: {
    label: "Open",
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
  },
  acknowledged: {
    label: "Acknowledged",
    color: "text-yellow-400",
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/30",
  },
  resolved: {
    label: "Resolved",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
  false_positive: {
    label: "False Positive",
    color: "text-zinc-400",
    bg: "bg-zinc-500/10",
    border: "border-zinc-500/30",
  },
};

/** Fix availability display metadata. */
export const FIX_META: Record<
  FixAvailability,
  { label: string; color: string; icon: string }
> = {
  fix_available: {
    label: "Fix available",
    color: "text-emerald-400",
    icon: "✓",
  },
  no_known_fix: {
    label: "No known fix",
    color: "text-orange-400",
    icon: "⚠",
  },
  not_applicable: {
    label: "Not applicable",
    color: "text-zinc-400",
    icon: "—",
  },
  unknown: {
    label: "Unknown",
    color: "text-zinc-400",
    icon: "?",
  },
};
