"use client";

import { AlertTriangle, ExternalLink, Shield, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { Finding, FindingType, Severity } from "@/lib/findings";
import { FINDING_TYPE_META, SEVERITY_META } from "@/lib/findings";
import { listRunFindings } from "@/lib/findings-api";

import { FindingSeverityBadge } from "./finding-severity-badge";
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

type FindingsSectionProps = {
  analysisRunId: string;
  /** When true, keep polling for new findings (run is still active). */
  isRunActive: boolean;
};

export function FindingsSection({
  analysisRunId,
  isRunActive,
}: FindingsSectionProps) {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [severityFilter, setSeverityFilter] = useState<Severity | "">("");
  const [typeFilter, setTypeFilter] = useState<FindingType | "">("");
  const requestSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    try {
      const result = await listRunFindings(analysisRunId, {
        severity: severityFilter || undefined,
        finding_type: typeFilter || undefined,
        page_size: 100,
      });
      if (seq !== requestSeq.current) return;
      setFindings(result.items);
      setTotal(result.total);
      setError(null);
    } catch (err) {
      if (seq !== requestSeq.current) return;
      setError(err);
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [analysisRunId, severityFilter, typeFilter]);

  // Initial fetch and refetch on filter change.
  // `.then/.catch/.finally` keeps setState out of the synchronous effect body.
  useEffect(() => {
    let cancelled = false;
    listRunFindings(analysisRunId, {
      severity: severityFilter || undefined,
      finding_type: typeFilter || undefined,
      page_size: 100,
    })
      .then((result) => {
        if (cancelled) return;
        setFindings(result.items);
        setTotal(result.total);
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
  }, [analysisRunId, severityFilter, typeFilter]);

  // Poll while run is active
  useEffect(() => {
    if (!isRunActive) return;
    const interval = window.setInterval(() => {
      void load();
    }, 3000);
    return () => window.clearInterval(interval);
  }, [isRunActive, load]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Shield className="size-4 text-primary" aria-hidden />
            Security findings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
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
            Could not load findings
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
          <Button variant="outline" size="sm" className="mt-3" onClick={() => void load()}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="size-4 text-primary" aria-hidden />
              Security findings
              {total > 0 ? (
                <Badge variant="secondary" className="ml-1">
                  {total}
                </Badge>
              ) : null}
            </CardTitle>
            <CardDescription className="text-xs">
              {isRunActive
                ? "The scan is in progress — findings appear as they are discovered."
                : total === 0
                  ? "No security findings detected by this scan."
                  : `${total} finding${total === 1 ? "" : "s"} detected.`}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="h-8 rounded-lg border border-input bg-transparent px-2 text-xs text-foreground"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as Severity | "")}
              aria-label="Filter by severity"
            >
              <option value="">All severities</option>
              {(["critical", "high", "medium", "low", "unknown"] as Severity[]).map(
                (s) => (
                  <option key={s} value={s}>
                    {SEVERITY_META[s].label}
                  </option>
                ),
              )}
            </select>
            <select
              className="h-8 rounded-lg border border-input bg-transparent px-2 text-xs text-foreground"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as FindingType | "")}
              aria-label="Filter by type"
            >
              <option value="">All types</option>
              {(
                Object.entries(FINDING_TYPE_META) as [
                  FindingType,
                  { label: string },
                ][]
              ).map(([type, meta]) => (
                <option key={type} value={type}>
                  {meta.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {findings.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <ShieldCheck className="size-6 text-emerald-500" aria-hidden />
            <p className="text-sm font-medium text-foreground">
              {severityFilter || typeFilter
                ? "No findings match your filters"
                : "No security findings detected"}
            </p>
            <p className="max-w-sm text-xs text-muted-foreground">
              {severityFilter || typeFilter
                ? "Try removing a filter to see all findings."
                : "This repository appears clean based on the scan performed."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border/60">
            {findings.map((finding) => (
              <li key={finding.id} className="py-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <FindingSeverityBadge severity={finding.severity} />
                      <Badge variant="outline" className="text-xs">
                        {FINDING_TYPE_META[finding.finding_type]?.label ?? finding.finding_type}
                      </Badge>
                      {finding.vulnerability_id ? (
                        <Badge variant="secondary" className="font-mono text-xs">
                          {finding.vulnerability_id}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-1.5 text-sm font-medium text-foreground">
                      {finding.title}
                    </p>
                    {finding.description ? (
                      <p className="mt-0.5 text-xs leading-5 text-muted-foreground line-clamp-2">
                        {finding.description}
                      </p>
                    ) : null}
                    <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
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
                      {finding.location ? (
                        <span className="truncate max-w-[200px]" title={finding.location}>
                          File: {finding.location}
                        </span>
                      ) : null}
                      <span className="text-muted-foreground/60">
                        {finding.scanner} {finding.scanner_version}
                      </span>
                    </div>
                  </div>
                  {finding.references.length > 0 ? (
                    <a
                      href={finding.references[0]}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="shrink-0 inline-flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80"
                    >
                      Reference <ExternalLink className="size-3" aria-hidden />
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
