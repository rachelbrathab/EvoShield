"use client";

import {
  AlertTriangle,
  ArrowLeft,
  Clock,
  GitBranch,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Tag,
  Trash2,
  User,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  isRunActive,
  isRunTerminal,
  type AnalysisRun,
} from "@/lib/analysis";
import { cancelAnalysis, deleteAnalysis, getAnalysis } from "@/lib/analysis-api";
import { formatDate, relativeTime } from "@/lib/format";

import { AnalysisRunStatusBadge } from "@/components/analysis/analysis-run-status-badge";
import { AnalysisTimeline } from "@/components/analysis/analysis-timeline";
import { FindingsSection } from "@/components/analysis/findings-section";
import { IntelligenceSection } from "@/components/analysis/intelligence-section";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const POLL_MS = 2000;

function formatDurationMs(ms: number | null): string {
  if (ms === null) return "–";
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

export default function AnalysisDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [working, setWorking] = useState(false);

  // Initial fetch. `.then/.catch/.finally` keeps setState out of the
  // synchronous effect body (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    getAnalysis(params.id)
      .then((data) => {
        if (!cancelled) {
          setRun(data);
          setError(null);
        }
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
  }, [params.id]);

  // Poll while the run is active so the user watches QUEUED → RUNNING →
  // terminal live. setState happens only inside the interval callback.
  useEffect(() => {
    if (!run || isRunTerminal(run.status)) return;
    const interval = window.setInterval(() => {
      getAnalysis(params.id)
        .then((fresh) => setRun(fresh))
        .catch(() => {
          // Transient poll errors are ignored; the page keeps its last state.
        });
    }, POLL_MS);
    return () => window.clearInterval(interval);
  }, [run, params.id]);

  const load = useCallback(async () => {
    try {
      setRun(await getAnalysis(params.id));
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  async function handleCancel() {
    if (!run) return;
    setWorking(true);
    try {
      const result = await cancelAnalysis(run.id);
      setRun(result.run);
      toast.success("Analysis cancelled");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setWorking(false);
    }
  }

  async function handleDelete() {
    if (!run) return;
    setWorking(true);
    try {
      await deleteAnalysis(run.id);
      toast.success("Analysis run deleted");
      router.push("/app/analysis");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
      setWorking(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-5" aria-label="Loading analysis">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-24 w-full rounded-xl" />
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4">
        <Link
          href="/app/analysis"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to analysis history
        </Link>
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <AlertTriangle className="size-6 text-destructive" aria-hidden />
            <div>
              <p className="text-sm font-medium text-foreground">
                Analysis run unavailable
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {error instanceof Error ? error.message : "Unknown error"}
              </p>
            </div>
            <Button variant="outline" onClick={() => void load()}>
              <RefreshCw className="size-4" />
              Try again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <Link
        href="/app/analysis"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to analysis history
      </Link>

      {/* Header */}
      <Card>
        <CardContent className="space-y-4 pt-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 items-start gap-3">
              <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
                <ShieldCheck className="size-5" aria-hidden />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="truncate text-xl font-semibold tracking-tight text-foreground">
                    {run.repository_full_name ?? "Analysis run"}
                  </h2>
                  <AnalysisRunStatusBadge status={run.status} />
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {isRunActive(run.status)
                    ? "The pipeline is executing — this page updates live."
                    : "This run has reached a terminal state."}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              {isRunActive(run.status) ? (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={working}
                  onClick={() => void handleCancel()}
                >
                  {working ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <XCircle className="size-3.5" />
                  )}
                  Cancel run
                </Button>
              ) : null}
              {isRunTerminal(run.status) ? (
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={working}
                  onClick={() => void handleDelete()}
                >
                  <Trash2 className="size-3.5" />
                  Delete run
                </Button>
              ) : null}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3">
        <MetaCard
          icon={User}
          label="Triggered by"
          value={run.triggered_by === "user" ? "Manual (user)" : run.triggered_by}
        />
        <MetaCard
          icon={Tag}
          label="Pipeline version"
          value={run.analysis_version}
        />
        <MetaCard
          icon={Clock}
          label="Duration"
          value={formatDurationMs(run.duration_ms)}
        />
      </div>

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Clock className="size-4 text-primary" aria-hidden />
            Execution timeline
          </CardTitle>
          <CardDescription className="text-xs">
            The run lifecycle — queue, dispatch, and outcome with timestamps.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AnalysisTimeline run={run} />
        </CardContent>
      </Card>

      {/* Metadata */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <GitBranch className="size-4 text-primary" aria-hidden />
            Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
            <Detail label="Run ID" value={run.id} />
            <Detail
              label="Repository"
              value={run.repository_full_name ?? run.repository_id}
              href={run.repository_id ? `/app/repositories/${run.repository_id}` : undefined}
            />
            <Detail label="Queued" value={relativeTime(run.created_at)} />
            <Detail label="Started" value={run.started_at ? relativeTime(run.started_at) : "—"} />
            <Detail label="Completed" value={run.completed_at ? relativeTime(run.completed_at) : "—"} />
            <Detail label="Created" value={formatDate(run.created_at)} />
          </dl>
          {run.failure_reason ? (
            <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 p-3">
              <p className="text-xs font-semibold text-red-400">
                Failure reason
              </p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                {run.failure_reason}
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Repository Intelligence (Sprint 6) */}
      <IntelligenceSection
        analysisRunId={run.id}
        isRunActive={isRunActive(run.status)}
      />

      {/* Security findings (Sprint 5A) */}
      <FindingsSection
        analysisRunId={run.id}
        isRunActive={isRunActive(run.status)}
      />
    </div>
  );
}

function MetaCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-4">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-4" aria-hidden />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="truncate text-sm font-semibold text-foreground">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function Detail({
  label,
  value,
  href,
}: {
  label: string;
  value: string;
  href?: string;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium text-foreground">
        {href ? (
          <Link
            href={href}
            className="text-primary transition-colors hover:underline"
          >
            {value}
          </Link>
        ) : (
          value
        )}
      </dd>
    </div>
  );
}
