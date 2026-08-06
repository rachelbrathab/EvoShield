/**
 * Analysis run domain types (Sprint 4A).
 *
 * Mirrors the backend `AnalysisRunRead` contract
 * (apps/backend/app/domains/analysis/schemas.py). The run-level status
 * vocabulary is distinct from the repository-level `AnalysisStatus` — a run
 * tracks one execution (queued → running → completed/failed/cancelled),
 * while the repository row holds the *latest* lifecycle state.
 */

export type AnalysisRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/** Wire shape of the backend `AnalysisRunRead` schema. */
export type AnalysisRun = {
  id: string;
  repository_id: string;
  /** Populated from the ownership join — the repository's `owner/name`. */
  repository_full_name: string | null;
  triggered_by: string;
  status: AnalysisRunStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  analysis_version: string;
  failure_reason: string | null;
  created_at: string | null;
  updated_at: string | null;
};

/** Paginated `GET /analysis` response. */
export type AnalysisRunPage = {
  items: AnalysisRun[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

/** Result of `POST /repositories/{id}/analysis`. */
export type AnalysisRunCreateResponse = {
  run: AnalysisRun;
};

/** Result of `POST /analysis/{id}/cancel`. */
export type AnalysisRunCancelResponse = {
  run: AnalysisRun;
};

export type AnalysisRunStatusMeta = {
  /** Human-readable label rendered next to the dot. */
  label: string;
  /** Tailwind class for the status dot color. */
  dot: string;
  /** One-line description, used in legends and tooltips. */
  description: string;
};

export const ANALYSIS_RUN_STATUS_META: Record<
  AnalysisRunStatus,
  AnalysisRunStatusMeta
> = {
  queued: {
    label: "Queued",
    dot: "bg-amber-400",
    description: "Waiting for a free execution slot.",
  },
  running: {
    label: "Running",
    dot: "bg-blue-500",
    description: "The analysis pipeline is executing.",
  },
  completed: {
    label: "Completed",
    dot: "bg-emerald-500",
    description: "The run finished successfully.",
  },
  failed: {
    label: "Failed",
    dot: "bg-red-500",
    description: "The run did not complete.",
  },
  cancelled: {
    label: "Cancelled",
    dot: "bg-zinc-500",
    description: "The run was cancelled.",
  },
};

/** All run statuses in lifecycle order — handy for filters and timelines. */
export const ANALYSIS_RUN_STATUSES: AnalysisRunStatus[] = [
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
];

/** Terminal states: the run can no longer transition. */
export function isRunTerminal(status: AnalysisRunStatus): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

/** Active states: still cancellable. */
export function isRunActive(status: AnalysisRunStatus): boolean {
  return status === "queued" || status === "running";
}
