/**
 * Findings API client — wraps the backend findings endpoints
 * (`/api/v1/analysis/{id}/findings` and `/api/v1/analysis/repositories/{id}/findings`).
 * Reuses the shared `apiFetch` helper from `@/lib/api`.
 */

import { apiFetch } from "@/lib/api";
import type { FindingPage, FindingType, Severity } from "@/lib/findings";

export type FindingListParams = {
  page?: number;
  page_size?: number;
  severity?: Severity;
  finding_type?: FindingType;
};

function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

/** List findings for a specific analysis run. */
export async function listRunFindings(
  analysisId: string,
  params: FindingListParams = {},
): Promise<FindingPage> {
  return apiFetch<FindingPage>(
    `/api/v1/analysis/${analysisId}/findings${buildQuery({ ...params })}`,
  );
}

/** List findings for all runs of a repository. */
export async function listRepositoryFindings(
  repositoryId: string,
  params: FindingListParams = {},
): Promise<FindingPage> {
  return apiFetch<FindingPage>(
    `/api/v1/analysis/repositories/${repositoryId}/findings${buildQuery({ ...params })}`,
  );
}
