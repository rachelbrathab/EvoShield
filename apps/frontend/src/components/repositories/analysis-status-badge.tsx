/**
 * Placeholder analysis-status badge for repository cards and detail pages.
 *
 * Sprint 3 preparation: renders a repository's `analysis_status` as a
 * colored-dot badge (⚪ 🟡 🔵 🟢 🔴 vocabulary). No analysis functionality —
 * the status value is supplied by the caller; new repositories default to
 * "Not Analyzed".
 */

import { Badge } from "@/components/ui/badge";
import {
  ANALYSIS_STATUS_META,
  type AnalysisStatus,
} from "@/lib/repository";
import { cn } from "@/lib/utils";

export function AnalysisStatusBadge({
  status = "not_analyzed",
  className,
}: {
  status?: AnalysisStatus;
  className?: string;
}) {
  const meta = ANALYSIS_STATUS_META[status];
  const isAnalyzing = status === "analyzing";

  return (
    <Badge
      variant="outline"
      className={cn("gap-1.5 text-xs", isAnalyzing && "border-blue-500/40", className)}
    >
      <span
        aria-hidden
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          meta.dot,
          isAnalyzing && "animate-pulse",
        )}
      />
      {meta.label}
    </Badge>
  );
}
