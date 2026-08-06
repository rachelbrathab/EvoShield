/**
 * Analysis API client — wraps the backend analysis endpoints
 * (`/api/v1/analysis/*` and `/api/v1/repositories/{id}/analysis`). Reuses the
 * shared `apiFetch` helper and error contract from `@/lib/api`.
 */

import { apiFetch } from "@/lib/api";
import type {
  AnalysisRun,
  AnalysisRunCancelResponse,
  AnalysisRunCreateResponse,
  AnalysisRunPage,
  AnalysisRunStatus,
} from "@/lib/analysis";

export type AnalysisListParams = {
  page?: number;
  page_size?: number;
  repository_id?: string;
  status?: AnalysisRunStatus;
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

/** Start a run for a repository. 409 when one is already active. */
export async function createAnalysis(
  repositoryId: string,
): Promise<AnalysisRunCreateResponse> {
  return apiFetch<AnalysisRunCreateResponse>(
    `/api/v1/repositories/${repositoryId}/analysis`,
    { method: "POST" },
  );
}

/** List the user's runs, newest first, with optional filters. */
export async function listAnalysis(
  params: AnalysisListParams = {},
): Promise<AnalysisRunPage> {
  return apiFetch<AnalysisRunPage>(
    `/api/v1/analysis${buildQuery({ ...params })}`,
  );
}

/** Get one run (404 when not owned). */
export async function getAnalysis(id: string): Promise<AnalysisRun> {
  return apiFetch<AnalysisRun>(`/api/v1/analysis/${id}`);
}

/** List runs for one repository. */
export async function listRepositoryAnalysis(
  repositoryId: string,
  params: Omit<AnalysisListParams, "repository_id"> = {},
): Promise<AnalysisRunPage> {
  return apiFetch<AnalysisRunPage>(
    `/api/v1/repositories/${repositoryId}/analysis${buildQuery(params)}`,
  );
}

/** Cancel a queued or running run. */
export async function cancelAnalysis(
  id: string,
): Promise<AnalysisRunCancelResponse> {
  return apiFetch<AnalysisRunCancelResponse>(`/api/v1/analysis/${id}/cancel`, {
    method: "POST",
  });
}

/** Delete a terminal run. */
export async function deleteAnalysis(id: string): Promise<void> {
  await apiFetch<unknown>(`/api/v1/analysis/${id}`, { method: "DELETE" });
}
