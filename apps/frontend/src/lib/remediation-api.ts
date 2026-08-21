/**
 * Remediation API client (Sprint 7).
 *
 * Fetches remediation intelligence and manages finding status updates.
 */

import type {
  AnalysisRemediation,
  RemediationStatusUpdate,
} from "@/lib/remediation";
import { apiFetch } from "@/lib/api";

/**
 * Get remediation intelligence for an analysis run.
 */
export async function getRemediation(
  analysisId: string,
): Promise<AnalysisRemediation> {
  return apiFetch<AnalysisRemediation>(
    `/api/v1/analysis/${analysisId}/remediation`,
  );
}

/**
 * Update a finding's remediation status.
 */
export async function updateFindingStatus(
  analysisId: string,
  findingId: string,
  update: RemediationStatusUpdate,
): Promise<{ finding_id: string; status: string; updated_at: string }> {
  return apiFetch(
    `/api/v1/analysis/${analysisId}/findings/${findingId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify(update),
    },
  );
}
