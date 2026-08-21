"use client";

import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowRight,
  CheckCircle,
  Shield,
  Target,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import type {
  RepositoryIntelligence,
  RiskFactor,
  PriorityFinding,
  ScannerCoverage,
  TrendInfo,
} from "@/lib/intelligence";
import {
  RISK_LEVEL_META,
  TREND_META,
} from "@/lib/intelligence";
import { getIntelligence } from "@/lib/intelligence-api";

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

type IntelligenceSectionProps = {
  analysisRunId: string;
  isRunActive: boolean;
};

export function IntelligenceSection({
  analysisRunId,
  isRunActive,
}: IntelligenceSectionProps) {
  const [intel, setIntel] = useState<RepositoryIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const requestSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    try {
      const data = await getIntelligence(analysisRunId);
      if (seq !== requestSeq.current) return;
      setIntel(data);
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
    getIntelligence(analysisRunId)
      .then((data) => {
        if (cancelled) return;
        setIntel(data);
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

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Shield className="size-4 text-primary" aria-hidden />
            Security posture
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
            Could not load intelligence
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {error instanceof Error ? error.message : "Unknown error"}
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

  if (!intel) return null;

  // Don't show intelligence for non-completed analyses
  if (intel.analysis_status !== "completed") {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <Shield className="mx-auto size-6 text-muted-foreground" aria-hidden />
          <p className="mt-2 text-sm font-medium text-foreground">
            Security analysis is not available yet.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Intelligence is computed after the analysis completes.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Risk Score Card */}
      <RiskScoreCard intel={intel} />

      {/* Severity Counts */}
      <SeverityCountsCard intel={intel} />

      {/* Risk Factors */}
      {intel.risk_factors.length > 0 ? (
        <RiskFactorsCard factors={intel.risk_factors} />
      ) : null}

      {/* Top Findings */}
      {intel.top_findings.length > 0 ? (
        <PriorityFindingsCard findings={intel.top_findings} />
      ) : null}

      {/* Scanner Coverage */}
      <ScannerCoverageCard coverage={intel.scanner_coverage} />

      {/* Trend */}
      {intel.trend.has_previous ? <TrendCard trend={intel.trend} /> : null}

      {/* Summary */}
      <Card>
        <CardContent className="pt-4">
          <p className="text-xs leading-5 text-muted-foreground">
            {intel.summary}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function RiskScoreCard({ intel }: { intel: RepositoryIntelligence }) {
  const meta = RISK_LEVEL_META[intel.risk_level];
  return (
    <Card>
      <CardContent className="flex items-center justify-between pt-4">
        <div>
          <p className="text-xs text-muted-foreground">Risk Score</p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-bold tabular-nums text-foreground">
              {Math.round(intel.risk_score)}
            </span>
            <span className="text-sm text-muted-foreground">/ 100</span>
          </div>
        </div>
        <div
          className={`rounded-lg border px-3 py-1.5 text-sm font-semibold ${meta.bg} ${meta.color} ${meta.border}`}
        >
          {meta.label}
        </div>
      </CardContent>
    </Card>
  );
}

function SeverityCountsCard({
  intel,
}: {
  intel: RepositoryIntelligence;
}) {
  const { severity_counts: s } = intel;
  const items = [
    { label: "Critical", count: s.critical, color: "text-red-400" },
    { label: "High", count: s.high, color: "text-orange-400" },
    { label: "Medium", count: s.medium, color: "text-yellow-400" },
    { label: "Low", count: s.low, color: "text-blue-400" },
  ];

  return (
    <div className="grid grid-cols-4 gap-3">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="flex flex-col items-center py-3">
            <span
              className={`text-2xl font-bold tabular-nums ${item.color}`}
            >
              {item.count}
            </span>
            <span className="text-[11px] text-muted-foreground">
              {item.label}
            </span>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function RiskFactorsCard({
  factors,
}: {
  factors: RiskFactor[];
}) {
  const severityIcon: Record<string, string> = {
    critical: "🔴",
    high: "🟠",
    medium: "🟡",
    low: "🔵",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Target className="size-4 text-primary" aria-hidden />
          Risk Factors
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {factors.map((factor) => (
            <li
              key={factor.category}
              className="flex items-center justify-between text-sm"
            >
              <span className="flex items-center gap-2">
                <span>{severityIcon[factor.severity] ?? "⚪"}</span>
                <span className="text-foreground">{factor.message}</span>
              </span>
              <Badge variant="secondary" className="ml-2 text-xs">
                {factor.count}
              </Badge>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function PriorityFindingsCard({
  findings,
}: {
  findings: PriorityFinding[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="size-4 text-primary" aria-hidden />
          Priority Findings
        </CardTitle>
        <CardDescription className="text-xs">
          What to investigate first
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border/60">
          {findings.map((f) => (
            <li key={f.id} className="py-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge
                      variant="outline"
                      className={`text-xs ${
                        f.severity === "critical"
                          ? "border-red-500/50 text-red-400"
                          : f.severity === "high"
                            ? "border-orange-500/50 text-orange-400"
                            : ""
                      }`}
                    >
                      {f.severity}
                    </Badge>
                    <Badge variant="secondary" className="text-xs">
                      {f.finding_type}
                    </Badge>
                    {f.vulnerability_id ? (
                      <Badge
                        variant="outline"
                        className="font-mono text-xs"
                      >
                        {f.vulnerability_id}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm font-medium text-foreground line-clamp-1">
                    {f.title}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {f.priority_reason}
                  </p>
                </div>
                <div className="shrink-0 text-right text-xs text-muted-foreground">
                  {f.location ? (
                    <span className="truncate max-w-[120px] block" title={f.location}>
                      {f.location}
                    </span>
                  ) : null}
                  <span className="text-muted-foreground/60">
                    {f.scanner}
                  </span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function ScannerCoverageCard({
  coverage,
}: {
  coverage: ScannerCoverage;
}) {
  const statusIcon = (status: string) => {
    if (status === "completed") return <CheckCircle className="size-3.5 text-emerald-500" />;
    if (status === "failed") return <AlertTriangle className="size-3.5 text-red-400" />;
    return <span className="size-3.5 inline-block rounded-full bg-muted-foreground/30" />;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Shield className="size-4 text-primary" aria-hidden />
          Scanner Coverage
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-1.5">
          {coverage.scanner_details.map((scanner) => (
            <li
              key={scanner.name}
              className="flex items-center justify-between text-sm"
            >
              <span className="flex items-center gap-2">
                {statusIcon(scanner.status)}
                <span className="font-medium capitalize text-foreground">
                  {scanner.name}
                </span>
              </span>
              <span className="text-xs text-muted-foreground">
                {scanner.finding_count !== null
                  ? `${scanner.finding_count} findings`
                  : scanner.status}
              </span>
            </li>
          ))}
        </ul>
        {coverage.total_scanners > 0 ? (
          <p className="mt-2 text-[11px] text-muted-foreground">
            {coverage.completed_scanners} of {coverage.total_scanners}{" "}
            scanners completed
            {coverage.failed_scanners > 0
              ? ` (${coverage.failed_scanners} failed)`
              : ""}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TrendCard({ trend }: { trend: TrendInfo }) {
  if (!trend.trend) return null;
  const meta = TREND_META[trend.trend];
  const Icon =
    trend.trend === "improving"
      ? ArrowDown
      : trend.trend === "worsening"
        ? ArrowUp
        : ArrowRight;

  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3">
        <Icon className={`size-4 ${meta.color}`} aria-hidden />
        <div>
          <span className={`text-sm font-medium ${meta.color}`}>
            {meta.label}
          </span>
          {trend.finding_delta !== null ? (
            <span className="ml-2 text-xs text-muted-foreground">
              {trend.finding_delta > 0 ? "+" : ""}
              {trend.finding_delta} finding
              {Math.abs(trend.finding_delta) !== 1 ? "s" : ""}
            </span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
