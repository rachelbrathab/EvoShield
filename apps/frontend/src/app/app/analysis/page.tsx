"use client";

import { Activity, GitBranch, Loader2, RefreshCw, Trash2, XCircle } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  ANALYSIS_RUN_STATUSES,
  ANALYSIS_RUN_STATUS_META,
  isRunActive,
  isRunTerminal,
  type AnalysisRun,
  type AnalysisRunStatus,
} from "@/lib/analysis";
import {
  cancelAnalysis,
  deleteAnalysis,
  listAnalysis,
} from "@/lib/analysis-api";
import { compactNumber, relativeTime } from "@/lib/format";

import { AnalysisRunStatusBadge } from "@/components/analysis/analysis-run-status-badge";
import { RepositoryPagination } from "@/components/repositories/repository-pagination";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const PAGE_SIZE = 15;

export default function AnalysisPage() {
  return (
    <Suspense fallback={<AnalysisSkeleton />}>
      <AnalysisHistory />
    </Suspense>
  );
}

function AnalysisHistory() {
  const searchParams = useSearchParams();
  const repositoryId = searchParams.get("repository_id") ?? undefined;

  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<"" | AnalysisRunStatus>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const listParams = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      status: status || undefined,
      repository_id: repositoryId,
    }),
    [page, status, repositoryId],
  );

  const load = useCallback(async () => {
    try {
      const result = await listAnalysis(listParams);
      setRuns(result.items);
      setTotal(result.total);
      setTotalPages(result.total_pages);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [listParams]);

  // Initial + filter-driven fetch. `.then/.catch/.finally` keeps setState out
  // of the synchronous effect body (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    listAnalysis(listParams)
      .then((result) => {
        if (cancelled) return;
        setRuns(result.items);
        setTotal(result.total);
        setTotalPages(result.total_pages);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [listParams]);

  async function handleCancel(run: AnalysisRun) {
    setCancellingId(run.id);
    try {
      const result = await cancelAnalysis(run.id);
      toast.success(
        `Cancelled ${run.repository_full_name ?? "analysis"} run`,
      );
      setRuns((current) =>
        current.map((item) => (item.id === run.id ? result.run : item)),
      );
      void load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setCancellingId(null);
    }
  }

  async function handleDelete(run: AnalysisRun) {
    try {
      await deleteAnalysis(run.id);
      toast.success("Analysis run deleted");
      setConfirmDeleteId(null);
      void load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  const selectClass =
    "h-8 rounded-lg border border-input bg-transparent px-2 text-sm text-foreground transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <section className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-foreground">
            <Activity className="size-5 text-primary" aria-hidden />
            Analysis history
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {repositoryId
              ? "Runs for the selected repository — lifecycle only, no findings yet."
              : `${total} ${total === 1 ? "run" : "runs"} across your repositories — lifecycle only, no findings yet.`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className={selectClass}
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as "" | AnalysisRunStatus);
              setPage(1);
            }}
            aria-label="Filter runs by status"
          >
            <option value="">All statuses</option>
            {ANALYSIS_RUN_STATUSES.map((value) => (
              <option key={value} value={value}>
                {ANALYSIS_RUN_STATUS_META[value].label}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="size-3.5" />
            Refresh
          </Button>
        </div>
      </section>

      {loading ? (
        <div className="space-y-2.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : error ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="py-8 text-center">
            <p className="text-sm font-medium text-foreground">
              Could not load analysis history
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => void load()}
            >
              Try again
            </Button>
          </CardContent>
        </Card>
      ) : runs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Activity className="size-6" aria-hidden />
            </div>
            <p className="text-sm font-medium text-foreground">
              {status ? "No runs match this status" : "No analysis runs yet"}
            </p>
            <p className="max-w-sm text-xs leading-5 text-muted-foreground">
              {status
                ? "Try a different status filter."
                : "Open a repository and click “Run analysis” to queue the first run."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <ul className="space-y-2.5">
            {runs.map((run) => (
              <li key={run.id}>
                <Card className="transition-colors hover:ring-primary/30">
                  <CardContent className="flex flex-col gap-3 py-3.5 sm:flex-row sm:items-center">
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <GitBranch className="size-4" aria-hidden />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          {run.repository_full_name ? (
                            <Link
                              href={`/app/repositories/${run.repository_id}`}
                              className="truncate text-sm font-medium text-foreground transition-colors hover:text-primary"
                            >
                              {run.repository_full_name}
                            </Link>
                          ) : (
                            <span className="truncate text-sm font-medium text-foreground">
                              Repository
                            </span>
                          )}
                          <AnalysisRunStatusBadge status={run.status} />
                        </div>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          Started {relativeTime(run.started_at ?? run.created_at)}
                          {run.duration_ms !== null
                            ? ` · took ${compactNumber(Math.round(run.duration_ms / 1000))}s`
                            : ""}
                        </p>
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        render={
                          <Link href={`/app/analysis/${run.id}`} />
                        }
                      >
                        View
                      </Button>
                      {isRunActive(run.status) ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={cancellingId === run.id}
                          onClick={() => void handleCancel(run)}
                        >
                          {cancellingId === run.id ? (
                            <Loader2 className="size-3.5 animate-spin" />
                          ) : (
                            <XCircle className="size-3.5" />
                          )}
                          Cancel
                        </Button>
                      ) : null}
                      {isRunTerminal(run.status) ? (
                        confirmDeleteId === run.id ? (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => void handleDelete(run)}
                          >
                            Confirm?
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setConfirmDeleteId(run.id)}
                            aria-label={`Delete run for ${run.repository_full_name ?? "repository"}`}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        )
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>

          <RepositoryPagination
            page={page}
            totalPages={totalPages}
            total={total}
            pageSize={PAGE_SIZE}
            noun="run"
            nounPlural="runs"
            showPageSize={false}
            onPageChange={setPage}
            onPageSizeChange={() => undefined}
          />
        </>
      )}
    </div>
  );
}

function AnalysisSkeleton() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-72" />
      </div>
      <div className="space-y-2.5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-xl" />
        ))}
      </div>
    </div>
  );
}
