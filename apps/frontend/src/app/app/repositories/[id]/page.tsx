"use client";

import {
  Activity,
  ArrowLeft,
  BookOpen,
  Check,
  Copy,
  ExternalLink,
  GitBranch,
  GitFork,
  Hash,
  Layers,
  Link2,
  Loader2,
  Lock,
  PlayCircle,
  RefreshCw,
  ShieldCheck,
  Star,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  compactNumber,
  formatDate,
  formatSizeKb,
  languageDotClass,
  relativeTime,
} from "@/lib/format";
import type { AnalysisRun } from "@/lib/analysis";
import {
  createAnalysis,
  listRepositoryAnalysis,
} from "@/lib/analysis-api";
import {
  repositoryCloneUrl,
  repositoryOwner,
  repositoryUrl,
  type Repository,
} from "@/lib/repository";
import {
  deleteRepository,
  getRepository,
  syncRepository,
} from "@/lib/repositories";

import { AnalysisRunStatusBadge } from "@/components/analysis/analysis-run-status-badge";
import { AnalysisStatusBadge } from "@/components/repositories/analysis-status-badge";
import { DeleteRepositoryDialog } from "@/components/repositories/delete-repository-dialog";
import { RepositoryErrorState } from "@/components/repositories/repository-error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function RepositoryDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [repository, setRepository] = useState<Repository | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [syncing, setSyncing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [copied, setCopied] = useState<"url" | "clone" | null>(null);
  const [recentRuns, setRecentRuns] = useState<AnalysisRun[]>([]);
  const [startingRun, setStartingRun] = useState(false);

  // Initial fetch. `.then/.catch/.finally` keeps setState out of the
  // synchronous effect body (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    getRepository(params.id)
      .then((repo) => {
        if (!cancelled) setRepository(repo);
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

  // Re-fetch from the "Try again" handler.
  const load = useCallback(async () => {
    try {
      setRepository(await getRepository(params.id));
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  // Recent analysis runs for this repository (Sprint 4A — lifecycle only).
  useEffect(() => {
    let cancelled = false;
    listRepositoryAnalysis(params.id, { page_size: 5 })
      .then((page) => {
        if (!cancelled) setRecentRuns(page.items);
      })
      .catch(() => {
        // The runs panel is supplementary — a failure must not break the page.
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  async function handleRunAnalysis() {
    if (!repository) return;
    setStartingRun(true);
    try {
      const result = await createAnalysis(repository.id);
      toast.success(
        `Analysis queued for ${repository.full_name} — you will see it transition through QUEUED → RUNNING → completed.`,
      );
      router.push(`/app/analysis/${result.run.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start analysis");
    } finally {
      setStartingRun(false);
    }
  }

  async function handleSync() {
    if (!repository) return;
    setSyncing(true);
    try {
      const result = await syncRepository(repository.id);
      setRepository(result.repository);
      if (result.warning) {
        toast.warning(result.warning);
      } else {
        toast.success(`Refreshed ${repository.full_name}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function copyText(text: string, kind: "url" | "clone") {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(null), 1500);
    } catch {
      toast.error("Could not copy — check clipboard permissions");
    }
  }

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-5" aria-label="Loading repository">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-28 w-full rounded-xl" />
        <div className="grid gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !repository) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-4">
        <Link
          href="/app/repositories"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to repositories
        </Link>
        <RepositoryErrorState error={error} onRetry={() => void load()} />
      </div>
    );
  }

  const repo = repository;
  const cloneUrl = repositoryCloneUrl(repo);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <Link
        href="/app/repositories"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to repositories
      </Link>

      {/* Header */}
      <Card>
        <CardContent className="space-y-4 pt-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex min-w-0 items-start gap-3">
              <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
                <BookOpen className="size-5" aria-hidden />
              </div>
              <div className="min-w-0">
                <h2 className="truncate text-xl font-semibold tracking-tight text-foreground">
                  {repo.full_name}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {repo.description || "No description provided."}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <Button
                size="sm"
                disabled={startingRun}
                onClick={() => void handleRunAnalysis()}
              >
                {startingRun ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <PlayCircle className="size-3.5" />
                )}
                Run analysis
              </Button>
              {repo.html_url ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void copyText(repositoryUrl(repo), "url")}
                  aria-label="Copy repository URL"
                >
                  {copied === "url" ? (
                    <Check className="size-3.5" />
                  ) : (
                    <Link2 className="size-3.5" />
                  )}
                  {copied === "url" ? "Copied" : "Copy URL"}
                </Button>
              ) : null}
              {cloneUrl ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void copyText(cloneUrl, "clone")}
                  aria-label="Copy clone URL"
                >
                  {copied === "clone" ? (
                    <Check className="size-3.5" />
                  ) : (
                    <Copy className="size-3.5" />
                  )}
                  {copied === "clone" ? "Copied" : "Clone"}
                </Button>
              ) : null}
              {repo.html_url ? (
                <Button
                  variant="outline"
                  size="sm"
                  render={
                    <a href={repo.html_url} target="_blank" rel="noreferrer noopener" />
                  }
                >
                  <ExternalLink className="size-3.5" />
                  Open in GitHub
                </Button>
              ) : null}
              <Button variant="outline" size="sm" onClick={() => void handleSync()} disabled={syncing}>
                {syncing ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="size-3.5" />
                )}
                {syncing ? "Syncing…" : "Sync now"}
              </Button>
              <Button variant="destructive" size="sm" onClick={() => setConfirmDelete(true)}>
                <Trash2 className="size-3.5" />
                Remove
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <AnalysisStatusBadge status={repo.analysis_status} />
            {repo.is_private ? (
              <Badge variant="secondary" className="gap-1">
                <Lock className="size-3" aria-hidden /> Private
              </Badge>
            ) : (
              <Badge variant="outline">Public</Badge>
            )}
            {repo.language ? (
              <Badge variant="outline" className="gap-1.5">
                <span
                  aria-hidden
                  className={`size-1.5 rounded-full ${languageDotClass(repo.language)}`}
                />
                {repo.language}
              </Badge>
            ) : null}
            {repo.archived ? <Badge variant="outline">Archived</Badge> : null}
            {repo.disabled ? <Badge variant="outline">Disabled</Badge> : null}
            {!repo.is_active ? <Badge variant="destructive">Unavailable</Badge> : null}
          </div>
        </CardContent>
      </Card>

      {/* Statistics */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Star} label="Stars" value={compactNumber(repo.stars)} />
        <StatCard icon={GitFork} label="Forks" value={compactNumber(repo.forks)} />
        <StatCard icon={Hash} label="Open issues" value={compactNumber(repo.open_issues)} />
        <StatCard icon={Layers} label="Size" value={formatSizeKb(repo.size_kb)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* General information */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <GitBranch className="size-4 text-primary" aria-hidden />
              General information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
              <Detail label="Default branch" value={repo.default_branch || "–"} />
              <Detail label="Owner" value={repositoryOwner(repo.full_name)} />
              <Detail label="Provider" value={repo.provider} />
              <Detail label="Visibility" value={repo.is_private ? "Private" : "Public"} />
              <Detail label="Created on GitHub" value={formatDate(repo.provider_created_at)} />
              <Detail label="Last push" value={formatDate(repo.pushed_at)} />
            </dl>
          </CardContent>
        </Card>

        {/* Analysis information */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-4 text-primary" aria-hidden />
              Analysis information
            </CardTitle>
            <CardDescription className="text-xs leading-5">
              Security analysis arrives in a later sprint. This section is the
              lifecycle placeholder repositories already carry.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between rounded-lg bg-muted/50 p-3">
              <span className="text-xs text-muted-foreground">Current status</span>
              <AnalysisStatusBadge status={repo.analysis_status} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-border/70 p-3">
                <p className="text-xs text-muted-foreground">Health score</p>
                <p className="mt-1 text-2xl font-semibold text-foreground">—</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  Computed after analysis (Sprint 6)
                </p>
              </div>
              <div className="rounded-lg border border-border/70 p-3">
                <p className="text-xs text-muted-foreground">Last analysis</p>
                <p className="mt-1 text-sm font-medium text-foreground">
                  {repo.last_analysis_at ? relativeTime(repo.last_analysis_at) : "Never"}
                </p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {repo.last_analysis_at ? formatDate(repo.last_analysis_at) : "No run recorded"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Repository metadata */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Layers className="size-4 text-primary" aria-hidden />
              Repository metadata
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
              <Detail label="Full name" value={repo.full_name} />
              <Detail label="Provider ID" value={repo.provider_repo_id || "–"} />
              <Detail label="Tracked since" value={formatDate(repo.created_at)} />
              <Detail label="Last synced" value={relativeTime(repo.last_synced_at)} />
              <Detail label="Updated on GitHub" value={formatDate(repo.provider_updated_at)} />
              <Detail label="Archived" value={repo.archived ? "Yes" : "No"} />
              <Detail label="Disabled" value={repo.disabled ? "Yes" : "No"} />
              <Detail
                label="Repository URL"
                value={repo.html_url || "–"}
                href={repo.html_url || undefined}
              />
            </dl>
          </CardContent>
        </Card>

        {/* License */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpen className="size-4 text-primary" aria-hidden />
              License
            </CardTitle>
          </CardHeader>
          <CardContent>
            {repo.license ? (
              <div className="flex items-center gap-2 rounded-lg bg-muted/50 p-3">
                <Badge variant="secondary">{repo.license}</Badge>
                <p className="text-xs text-muted-foreground">
                  SPDX identifier reported by GitHub.
                </p>
              </div>
            ) : (
              <p className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
                This repository does not declare a license. Check with the owner
                before reusing its code.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Topics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Hash className="size-4 text-primary" aria-hidden />
            Topics
          </CardTitle>
        </CardHeader>
        <CardContent>
          {repo.topics.length === 0 ? (
            <p className="text-xs text-muted-foreground">No topics on this repository.</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {repo.topics.map((topic) => (
                <Badge key={topic} variant="secondary">
                  {topic}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent analysis runs (Sprint 4A) */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="size-4 text-primary" aria-hidden />
            Recent analysis runs
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            render={
              <Link href={`/app/analysis?repository_id=${repo.id}`} />
            }
          >
            View all runs
          </Button>
        </CardHeader>
        <CardContent>
          {recentRuns.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-6 text-center">
              <Activity className="size-5 text-muted-foreground" aria-hidden />
              <p className="text-xs text-muted-foreground">
                No analysis runs yet — click “Run analysis” to queue the first one.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-border/60">
              {recentRuns.map((run) => (
                <li key={run.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="flex min-w-0 items-center gap-2">
                    <AnalysisRunStatusBadge status={run.status} />
                    <Link
                      href={`/app/analysis/${run.id}`}
                      className="truncate text-xs text-muted-foreground transition-colors hover:text-primary"
                    >
                      {run.id.slice(0, 8)} · {relativeTime(run.created_at)}
                    </Link>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {run.duration_ms !== null
                      ? `${Math.round(run.duration_ms / 1000)}s`
                      : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <DeleteRepositoryDialog
        repository={confirmDelete ? repo : null}
        onOpenChange={(open) => {
          if (!open) setConfirmDelete(false);
        }}
        onConfirm={async (target) => {
          await deleteRepository(target.id);
          toast.success(`Removed ${target.full_name}`);
          router.push("/app/repositories");
          router.refresh();
        }}
      />
    </div>
  );
}

function StatCard({
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
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-lg font-semibold text-foreground">{value}</p>
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
          <a
            href={href}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex max-w-full items-center gap-1 truncate text-primary transition-colors hover:underline"
          >
            <span className="truncate">{value}</span>
            <ExternalLink className="size-3 shrink-0" aria-hidden />
          </a>
        ) : (
          value
        )}
      </dd>
    </div>
  );
}
