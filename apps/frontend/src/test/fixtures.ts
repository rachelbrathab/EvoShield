import type { AnalysisRun } from "@/lib/analysis";
import type { Repository } from "@/lib/repository";

/** A minimal-but-complete Repository fixture for component tests. */
export function makeRepository(overrides: Partial<Repository> = {}): Repository {
  return {
    id: "repo-id-1",
    owner_id: "user-1",
    provider: "github",
    provider_repo_id: "123",
    name: "evoshield",
    full_name: "octocat/evoshield",
    default_branch: "main",
    html_url: "https://github.com/octocat/evoshield",
    description: "Predictive software supply chain risk assessment",
    is_private: false,
    is_active: true,
    language: "Python",
    stars: 12_500,
    forks: 340,
    open_issues: 12,
    topics: ["security", "devsecops", "python"],
    license: "MIT",
    size_kb: 4096,
    archived: false,
    disabled: false,
    provider_created_at: "2023-05-01T00:00:00Z",
    provider_updated_at: "2024-01-15T10:00:00Z",
    pushed_at: "2024-02-01T10:00:00Z",
    last_synced_at: "2024-02-10T10:00:00Z",
    analysis_status: "not_analyzed",
    last_analysis_at: null,
    last_analysis_job_id: null,
    created_at: "2024-02-10T09:00:00Z",
    updated_at: "2024-02-10T10:00:00Z",
    ...overrides,
  };
}

/** A minimal-but-complete AnalysisRun fixture for component tests. */
export function makeAnalysisRun(
  overrides: Partial<AnalysisRun> = {},
): AnalysisRun {
  return {
    id: "run-id-1",
    repository_id: "repo-id-1",
    repository_full_name: "octocat/evoshield",
    triggered_by: "user",
    status: "queued",
    started_at: null,
    completed_at: null,
    duration_ms: null,
    analysis_version: "0.1.0",
    failure_reason: null,
    created_at: "2024-02-10T09:00:00Z",
    updated_at: "2024-02-10T09:00:00Z",
    ...overrides,
  };
}
