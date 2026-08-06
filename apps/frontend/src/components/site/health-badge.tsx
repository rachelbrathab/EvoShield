"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { fetchHealth } from "@/lib/api";

type Status = "checking" | "online" | "degraded" | "offline";

const STATUS_META: Record<Status, { label: string; dot: string }> = {
  checking: { label: "Checking API…", dot: "bg-zinc-400" },
  online: { label: "API online", dot: "bg-emerald-400" },
  degraded: { label: "API degraded", dot: "bg-amber-400" },
  offline: { label: "API offline", dot: "bg-rose-500" },
};

export function HealthBadge({ className }: { className?: string }) {
  const [status, setStatus] = useState<Status>("checking");
  const [version, setVersion] = useState<string | null>(null);

  const check = useCallback(async (signal?: AbortSignal) => {
    setStatus("checking");
    try {
      const health = await fetchHealth(signal);
      setVersion(health.version);
      setStatus(health.status === "ok" ? "online" : "degraded");
    } catch {
      setVersion(null);
      setStatus("offline");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // Defer the initial check out of the effect body so the synchronous
    // "checking" state update doesn't cascade renders from the effect.
    const timer = setTimeout(() => {
      void check(controller.signal);
    }, 0);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [check]);

  const meta = STATUS_META[status];

  return (
    <button
      type="button"
      onClick={() => void check()}
      title="Click to re-check API connectivity"
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs text-muted-foreground",
        "transition-colors hover:border-border hover:text-foreground",
        className,
      )}
    >
      <span className="relative flex h-2 w-2">
        {status === "checking" ? (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-zinc-400 opacity-60" />
        ) : null}
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", meta.dot)} />
      </span>
      <span className="tabular-nums">
        {meta.label}
        {version ? ` · v${version}` : ""}
      </span>
    </button>
  );
}
