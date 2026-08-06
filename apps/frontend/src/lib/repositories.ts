/**
 * Repository API client — wraps the backend repository endpoints
 * (`/api/v1/repositories/*`). Reuses the shared `apiFetch` helper and the
 * error contract from `@/lib/api`.
 */

import { apiFetch } from "@/lib/api";
import type {
  GitHubRepositoryCandidate,
  GitHubSearchPage,
  Repository,
  RepositoryImportResult,
  RepositoryListParams,
  RepositoryPage,
  RepositorySyncResult,
} from "@/lib/repository";

export async function listRepositories(
  params: RepositoryListParams = {},
): Promise<RepositoryPage> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return apiFetch<RepositoryPage>(
    `/api/v1/repositories${query ? `?${query}` : ""}`,
  );
}

export async function getRepository(id: string): Promise<Repository> {
  return apiFetch<Repository>(`/api/v1/repositories/${id}`);
}

export async function importRepository(
  fullName: string,
): Promise<RepositoryImportResult> {
  return apiFetch<RepositoryImportResult>("/api/v1/repositories/import", {
    method: "POST",
    body: JSON.stringify({ full_name: fullName }),
  });
}

export async function syncRepository(id: string): Promise<RepositorySyncResult> {
  return apiFetch<RepositorySyncResult>(`/api/v1/repositories/${id}/sync`, {
    method: "PATCH",
  });
}

export async function deleteRepository(id: string): Promise<void> {
  await apiFetch<unknown>(`/api/v1/repositories/${id}`, {
    method: "DELETE",
  });
}

/** Browse the user's GitHub repositories for the import dialog. */
export async function searchGitHubRepositories(
  params: { q?: string; page?: number; per_page?: number } = {},
): Promise<GitHubSearchPage> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return apiFetch<GitHubSearchPage>(
    `/api/v1/repositories/search${query ? `?${query}` : ""}`,
  );
}

/** A repository is already tracked if its id appears in this page. */
export function isTracked(
  candidate: GitHubRepositoryCandidate,
  tracked: Repository[],
): boolean {
  return tracked.some(
    (repo) => repo.provider_repo_id === candidate.provider_repo_id,
  );
}
