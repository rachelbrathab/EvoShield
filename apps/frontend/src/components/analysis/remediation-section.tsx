"use client";

import {
  AlertTriangle,
  Loader2,
  Wrench,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import type {
  AnalysisRemediation,
  FindingRemediation,
  RemediationStatus,
} from "@/lib/remediation";
import { FIX_META, STATUS_META } from "@/lib/remediation";
import {
  getRemediation,
  updateFindingStatus,
} from "@/lib/remediation-api";

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

type RemediationSectionProps = {
  analysisRunId: string;
  isRunActive: boolean;
};

export function RemediationSection({
  analysisRunId,
  isRunActive,
}: RemediationSectionProps) {
  const [data, setData] = useState<AnalysisRemediation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const requestSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    try {
      const result = await getRemediation(analysisRunId);
      if (seq !== requestSeq.current) return;
      setData(result);
      setError(null);
    } catch (err) {
      if (seq !== requestSeq.current) return;
      setError(err);
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [analysisRunId]);

  useEffect(() => {
    let cancelled = false;
    getRemediation(analysisRunId)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [analysisRunId]);

  // Poll while run is active
  useEffect(() => {
    if (!isRunActive) return;
    const interval = window.setInterval(() => {
      void load();
    }, 5000);
    return () => window.clearInterval(interval);
  }, [isRunActive, load]);

  async function handleStatusUpdate(
    findingId: string,
    status: RemediationStatus,
  ) {
    setUpdatingId(findingId);
    try {
      await updateFindingStatus(analysisRunId, findingId, { status });
      // Reload data after status update
      await load();
    } catch {
      // Status update failed — data remains unchanged
    } finally {
      setUpdatingId(null);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Wrench className="size-4 text-primary" aria-hidden />
            Remediation
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive/30 bg-destructive/5">
        <CardContent className="py-8 text-center">
          <AlertTriangle className="mx-auto size-5 text-destructive" aria-hidden />
          <p className="mt-2 text-sm font-medium text-foreground">
            Could not load remediation data
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => void load()}
          >
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.summary.total_findings === 0) return null;

  return (
    <div className="space-y-4">
      {/* Remediation Summary */}
      <RemediationSummaryCard data={data} />

      {/* Findings with remediation guidance */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Wrench className="size-4 text-primary" aria-hidden />
                Remediation Plan
              </CardTitle>
              <CardDescription className="text-xs">
                Findings prioritized by severity and fix availability
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ul className="divide-y divide-border/60">
            {data.findings.map((finding) => (
              <RemediationFindingCard
                key={finding.finding_id}
                finding={finding}
                onStatusUpdate={(status) =>
                  void handleStatusUpdate(finding.finding_id, status)
                }
                isUpdating={updatingId === finding.finding_id}
              />
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function RemediationSummaryCard({
  data,
}: {
  data: AnalysisRemediation;
}) {
  const { summary: s } = data;
  const rateColor =
    s.remediation_rate >= 80
      ? "text-emerald-400"
      : s.remediation_rate >= 50
        ? "text-yellow-400"
        : "text-red-400";

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Card>
        <CardContent className="flex flex-col items-center py-3">
          <span className="text-2xl font-bold tabular-nums text-red-400">
            {s.open_count}
          </span>
          <span className="text-[11px] text-muted-foreground">Open</span>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex flex-col items-center py-3">
          <span className="text-2xl font-bold tabular-nums text-yellow-400">
            {s.acknowledged_count}
          </span>
          <span className="text-[11px] text-muted-foreground">Acknowledged</span>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex flex-col items-center py-3">
          <span className="text-2xl font-bold tabular-nums text-emerald-400">
            {s.resolved_count}
          </span>
          <span className="text-[11px] text-muted-foreground">Resolved</span>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex flex-col items-center py-3">
          <span className={`text-2xl font-bold tabular-nums ${rateColor}`}>
            {Math.round(s.remediation_rate)}%
          </span>
          <span className="text-[11px] text-muted-foreground">
            Remediation Rate
          </span>
        </CardContent>
      </Card>
    </div>
  );
}

function RemediationFindingCard({
  finding,
  onStatusUpdate,
  isUpdating,
}: {
  finding: FindingRemediation;
  onStatusUpdate: (status: RemediationStatus) => void;
  isUpdating: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const statusMeta = STATUS_META[finding.status];
  const fixMeta = FIX_META[finding.fix_availability];

  return (
    <li className="py-3">
      <div className="flex flex-col gap-2">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge
                variant="outline"
                className={`text-xs ${
                  finding.severity === "critical"
                    ? "border-red-500/50 text-red-400"
                    : finding.severity === "high"
                      ? "border-orange-500/50 text-orange-400"
                      : ""
                }`}
              >
                {finding.severity}
              </Badge>
              <Badge variant="secondary" className="text-xs">
                {finding.finding_type}
              </Badge>
              <Badge
                variant="outline"
                className={`text-xs ${statusMeta.color} ${statusMeta.border}`}
              >
                {statusMeta.label}
              </Badge>
              {finding.vulnerability_id ? (
                <Badge variant="outline" className="font-mono text-xs">
                  {finding.vulnerability_id}
                </Badge>
              ) : null}
            </div>
            <p className="mt-1.5 text-sm font-medium text-foreground">
              {finding.title}
            </p>

            {/* Package info */}
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              {finding.package_name ? (
                <span>
                  Package:{" "}
                  <span className="font-medium text-foreground">
                    {finding.package_name}
                  </span>
                </span>
              ) : null}
              {finding.installed_version ? (
                <span>
                  Installed:{" "}
                  <span className="font-mono text-foreground">
                    {finding.installed_version}
                  </span>
                </span>
              ) : null}
              {finding.fixed_version ? (
                <span>
                  Fixed:{" "}
                  <span className="font-mono text-emerald-400">
                    {finding.fixed_version}
                  </span>
                </span>
              ) : null}
            </div>

            {/* Fix availability */}
            <div className="mt-1.5">
              <span className={`text-xs ${fixMeta.color}`}>
                {fixMeta.icon} {fixMeta.label}
              </span>
            </div>
          </div>

          {/* Status actions */}
          <div className="flex shrink-0 items-center gap-1">
            {isUpdating ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            ) : finding.status === "open" ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => onStatusUpdate("acknowledged")}
                >
                  Acknowledge
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => onStatusUpdate("resolved")}
                >
                  Resolve
                </Button>
              </>
            ) : finding.status === "acknowledged" ? (
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => onStatusUpdate("resolved")}
              >
                Resolve
              </Button>
            ) : null}
          </div>
        </div>

        {/* Expandable guidance */}
        <button
          type="button"
          className="text-left text-xs text-primary hover:text-primary/80"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Hide details" : "Show remediation details"}
        </button>

        {expanded ? (
          <div className="rounded-lg border border-border/60 bg-muted/30 p-3 space-y-2">
            <div>
              <p className="text-[11px] font-semibold text-muted-foreground uppercase">
                Why this matters
              </p>
              <p className="mt-0.5 text-xs leading-5 text-foreground">
                {finding.guidance.summary}
              </p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-muted-foreground uppercase">
                Recommended fix
              </p>
              <p className="mt-0.5 text-xs leading-5 text-foreground">
                {finding.guidance.recommendation}
              </p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-muted-foreground uppercase">
                Steps
              </p>
              <ol className="mt-0.5 list-decimal list-inside space-y-1">
                {finding.guidance.steps.map((step, i) => (
                  <li key={i} className="text-xs leading-5 text-foreground">
                    {step}
                  </li>
                ))}
              </ol>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>Scanner: {finding.scanner}</span>
              {finding.location ? <span>Location: {finding.location}</span> : null}
            </div>
          </div>
        ) : null}
      </div>
    </li>
  );
}
