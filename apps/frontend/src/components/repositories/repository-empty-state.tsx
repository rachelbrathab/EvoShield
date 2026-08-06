"use client";

import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Polished empty-state block for the repository module: an icon tile, a
 * title, a short message and an optional action. Used for "no repositories",
 * "no search results" and "no GitHub connection".
 */
export function RepositoryEmptyState({
  icon: Icon,
  title,
  message,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  message: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-4 rounded-xl border border-dashed border-border bg-muted/20 px-6 py-14 text-center",
        className,
      )}
    >
      <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
        <Icon className="size-6" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="mx-auto max-w-sm text-xs leading-5 text-muted-foreground">
          {message}
        </p>
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
