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
  if (!meta) {
    // Defensive: should never happen with the typed AnalysisStatus union,
    // but a future backend value must not crash the UI.
    return (
      <Badge variant="outline" className={cn("gap-1.5 text-xs", className)}>
        <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-zinc-400" />
        Unknown
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className={cn("gap-1.5 text-xs", className)}
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
