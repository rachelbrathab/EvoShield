/**
 * Repository domain types (Sprint 3A).
 *
 * Mirrors the backend `RepositoryRead` contract
 * (apps/backend/app/domains/github/schemas.py) plus the list/import/search
 * response shapes. The analysis-status vocabulary lives here so repository
 * cards and detail pages can render status before analysis ships (Sprint 4+).
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

  // GitHub metadata (Sprint 3A)
  language: string | null;
  stars: number;
  forks: number;
  open_issues: number;
  topics: string[];
  license: string | null;
  size_kb: number | null;
  archived: boolean;
  disabled: boolean;
  provider_created_at: string | null;
  provider_updated_at: string | null;
  pushed_at: string | null;
  last_synced_at: string | null;

  // Analysis status (Sprint 4+ pipelines drive this)
  analysis_status: AnalysisStatus;
  last_analysis_at: string | null;
  last_analysis_job_id: string | null;

  created_at: string | null;
  updated_at: string | null;
};

/** `GET /repositories` paginated response. */
export type RepositoryPage = {
  items: Repository[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

/** Sort keys accepted by `GET /repositories` (Sprint 3B added forks/language/size_kb). */
export type RepositorySortKey =
  | "name"
  | "stars"
  | "forks"
  | "language"
  | "size_kb"
  | "pushed_at"
  | "created_at"
  | "updated_at";

/** "Imported" recency presets — maps to the `imported_after` query param. */
export type ImportedRange = "" | "7d" | "30d" | "90d";

/** Query parameters for `GET /repositories`. */
export type RepositoryListParams = {
  page?: number;
  page_size?: number;
  q?: string;
  language?: string;
  visibility?: "public" | "private";
  analysis_status?: AnalysisStatus;
  archived?: boolean;
  disabled?: boolean;
  imported_after?: string;
  sort?: RepositorySortKey;
  order?: "asc" | "desc";
};

/** A fully-parsed view-model of the list toolbar (search/filter/sort/page). */
export type RepositoryListViewState = {
  q: string;
  language: string;
  visibility: "" | "public" | "private";
  status: "" | AnalysisStatus;
  imported: ImportedRange;
  archived: "" | "true" | "false";
  disabled: "" | "true" | "false";
  sort: RepositorySortKey;
  order: "asc" | "desc";
  page: number;
  pageSize: number;
};

/** A GitHub repository offered in the import browser (`GET /repositories/search`). */
export type GitHubRepositoryCandidate = {
  provider_repo_id: string;
  full_name: string;
  name: string;
  description: string | null;
  language: string | null;
  stars: number;
  is_private: boolean;
  html_url: string;
  pushed_at: string | null;
};

export type GitHubSearchPage = {
  items: GitHubRepositoryCandidate[];
  page: number;
  has_more: boolean;
};

/** Result of `POST /repositories/import` — idempotent by design. */
export type RepositoryImportResult = {
  repository: Repository;
  was_already_imported: boolean;
};

/** Result of `PATCH /repositories/{id}/sync`. */
export type RepositorySyncResult = {
  repository: Repository;
  warning: string | null;
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

/** The `owner` portion of a `owner/name` full name. */
export function repositoryOwner(fullName: string): string {
  return fullName.split("/")[0] ?? fullName;
}

/** The `name` portion of a `owner/name` full name. */
export function repositoryName(fullName: string): string {
  return fullName.split("/").slice(1).join("/") || fullName;
}

/** The browse URL of a tracked repository (falls back to GitHub when missing). */
export function repositoryUrl(repository: {
  html_url: string | null;
  full_name: string;
}): string {
  return repository.html_url ?? `https://github.com/${repository.full_name}`;
}

/** The `git clone` URL for a tracked repository. */
export function repositoryCloneUrl(repository: {
  full_name: string;
  is_private: boolean;
}): string {
  const path = repository.full_name.replace(/\/+/g, "/").replace(/^\/+|\/+$/g, "");
  if (!path) return "";
  const scheme = repository.is_private ? "git@github.com:" : "https://github.com/";
  return repository.is_private ? `${scheme}${path}.git` : `${scheme}${path}.git`;
}

/** Render an ISO date as `YYYY-MM-DD` for the `imported_after` query param. */
export function importedAfterIso(range: ImportedRange): string | undefined {
  if (!range) return undefined;
  const days = { "7d": 7, "30d": 30, "90d": 90 }[range];
  if (!days) return undefined;
  const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  return cutoff.toISOString();
}
