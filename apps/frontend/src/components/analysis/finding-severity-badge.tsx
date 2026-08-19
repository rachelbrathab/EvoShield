"use client";

import type { Severity } from "@/lib/findings";
import { SEVERITY_META } from "@/lib/findings";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function FindingSeverityBadge({ severity }: { severity: Severity }) {
  const meta = SEVERITY_META[severity];
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 border text-xs font-medium",
        meta.border,
        meta.bg,
        meta.color,
      )}
    >
      <span className={cn("size-1.5 rounded-full", meta.color.replace("text-", "bg-"))} aria-hidden />
      {meta.label}
    </Badge>
  );
}
