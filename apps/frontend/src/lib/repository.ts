/**
 * Repository domain types (Sprint 3+).
 *
 * Mirrors the backend `RepositoryRead` contract
 * (apps/backend/app/domains/github/schemas.py). The analysis-status
 * vocabulary lives here so repository cards and detail pages can render
 * status placeholders before analysis functionality ships (Sprint 4+).
 */

export type AnalysisStatus =
  | "not_analyzed"
  | "queued"
  | "analyzing"
  | "analyzed"
  | "failed"
  | "cancelled";

/** Wire shape of the backend `RepositoryRead` schema. */
export type Repository = {
  id: string;
  owner_id: string;
  provider: string;
  provider_repo_id: string | null;
  name: string;
  full_name: string;
  default_branch: string | null;
  html_url: string | null;
  description: string | null;
  is_private: boolean;
  is_active: boolean;
  analysis_status: AnalysisStatus;
  last_analysis_at: string | null;
  last_analysis_job_id: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type AnalysisStatusMeta = {
  /** Human-readable label rendered next to the dot. */
  label: string;
  /** Tailwind class for the status dot color. */
  dot: string;
  /** One-line description, used in legends and tooltips. */
  description: string;
};

export const ANALYSIS_STATUS_META: Record<AnalysisStatus, AnalysisStatusMeta> = {
  not_analyzed: {
    label: "Not Analyzed",
    dot: "bg-zinc-400",
    description: "No analysis has run yet.",
  },
  queued: {
    label: "Queued",
    dot: "bg-amber-400",
    description: "Waiting in the analysis queue.",
  },
  analyzing: {
    label: "Analyzing",
    dot: "bg-blue-500",
    description: "Analysis is running now.",
  },
  analyzed: {
    label: "Analyzed",
    dot: "bg-emerald-500",
    description: "The latest analysis completed.",
  },
  failed: {
    label: "Failed",
    dot: "bg-red-500",
    description: "The latest analysis did not complete.",
  },
  cancelled: {
    label: "Cancelled",
    dot: "bg-zinc-500",
    description: "Analysis was cancelled.",
  },
};

/** All statuses in lifecycle order — handy for legends and filters. */
export const ANALYSIS_STATUSES: AnalysisStatus[] = [
  "not_analyzed",
  "queued",
  "analyzing",
  "analyzed",
  "failed",
  "cancelled",
];
