"use client";

import {
  ANALYSIS_RUN_STATUS_META,
  type AnalysisRunStatus,
} from "@/lib/analysis";
import { cn } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";

/**
 * Status badge for an *analysis run* (queued/running/completed/failed/
 * cancelled). Distinct from `AnalysisStatusBadge`, which renders the
 * repository-level lifecycle status.
 */
export function AnalysisRunStatusBadge({
  status,
  className,
}: {
  status: AnalysisRunStatus;
  className?: string;
}) {
  const meta = ANALYSIS_RUN_STATUS_META[status];
  const isRunning = status === "running";

  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1.5 text-xs",
        isRunning && "border-blue-500/40 text-blue-300 dark:text-blue-400",
        status === "failed" && "border-red-500/40 text-red-400",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          meta.dot,
        )}
      />
      {meta.label}
    </Badge>
  );
}
