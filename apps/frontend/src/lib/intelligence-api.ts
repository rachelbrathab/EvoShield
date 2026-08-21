/**
 * Intelligence API client — wraps the backend intelligence endpoint
 * (`/api/v1/analysis/{id}/intelligence`). Reuses the shared `apiFetch`
 * helper from `@/lib/api`.
 */

import { apiFetch } from "@/lib/api";
import type { RepositoryIntelligence } from "@/lib/intelligence";

/** Get repository intelligence for an analysis run. */
export async function getIntelligence(
  analysisId: string,
): Promise<RepositoryIntelligence> {
  return apiFetch<RepositoryIntelligence>(
    `/api/v1/analysis/${analysisId}/intelligence`,
  );
}
