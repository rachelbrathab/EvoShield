"use client";

import { Check, Loader2, X } from "lucide-react";

import type { AnalysisRun } from "@/lib/analysis";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

type StepState = "done" | "active" | "pending" | "failed";

/**
 * Vertical execution timeline for one analysis run: Queued → Running →
 * outcome (Completed / Failed / Cancelled). The current state is highlighted;
 * completed steps show a check. Pure rendering — no logic beyond mapping the
 * run status to step states, so it is easy to test.
 */
export function AnalysisTimeline({ run }: { run: AnalysisRun }) {
  const outcomeLabel =
    run.status === "failed"
      ? "Failed"
      : run.status === "cancelled"
        ? "Cancelled"
        : "Completed";

  const outcomeState: StepState =
    run.status === "completed"
      ? "done"
      : run.status === "failed" || run.status === "cancelled"
        ? "failed"
        : "pending";

  const steps: Array<{
    key: string;
    label: string;
    time: string | null;
    state: StepState;
  }> = [
    {
      key: "queued",
      label: "Queued",
      time: run.created_at,
      state: run.status === "queued" ? "active" : "done",
    },
    {
      key: "running",
      label: "Running",
      time: run.started_at,
      state:
        run.status === "queued"
          ? "pending"
          : run.status === "running"
            ? "active"
            : "done",
    },
    {
      key: "outcome",
      label: outcomeLabel,
      time: run.completed_at,
      state: run.status === "queued" || run.status === "running" ? "pending" : outcomeState,
    },
  ];

  return (
    <ol aria-label="Analysis timeline" className="space-y-0">
      {steps.map((step, index) => (
        <li key={step.key} className="relative flex gap-3 pb-6 last:pb-0">
          {/* Connector line */}
          {index < steps.length - 1 ? (
            <span
              aria-hidden
              className={cn(
                "absolute top-6 left-[11px] h-[calc(100%-1.25rem)] w-px",
                step.state === "done" || step.state === "failed"
                  ? "bg-primary/40"
                  : "bg-border",
              )}
            />
          ) : null}

          <span
            aria-hidden
            className={cn(
              "z-10 flex size-6 shrink-0 items-center justify-center rounded-full ring-4 ring-background",
              step.state === "done" &&
                "bg-primary/15 text-primary",
              step.state === "active" && "bg-blue-500/15 text-blue-400",
              step.state === "failed" && "bg-red-500/15 text-red-400",
              step.state === "pending" && "bg-muted text-muted-foreground/50",
            )}
          >
            {step.state === "done" ? (
              <Check className="size-3.5" />
            ) : step.state === "active" ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : step.state === "failed" ? (
              <X className="size-3.5" />
            ) : (
              <span className="size-1.5 rounded-full bg-current" />
            )}
          </span>

          <div className="min-w-0 pt-0.5">
            <p
              className={cn(
                "text-sm font-medium",
                step.state === "pending" && "text-muted-foreground/60",
                step.state === "failed" && "text-red-400",
              )}
            >
              {step.label}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {step.time ? relativeTime(step.time) : "Waiting…"}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
