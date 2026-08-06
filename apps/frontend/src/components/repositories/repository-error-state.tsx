"use client";

import { AlertTriangle, ExternalLink, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { githubOAuthUrl } from "@/lib/api";
import { describeError } from "@/lib/repository-errors";

import { Button } from "@/components/ui/button";

/**
 * Code-aware error state for the repository module. Maps backend error codes
 * (`github_rate_limited`, `github_token_invalid`, `github_not_connected`,
 * `github_forbidden`, `not_found`, network failures) to friendly copy with
 * the right action: "Try again", "Reconnect GitHub", or a supplied fallback.
 */
export function RepositoryErrorState({
  error,
  onRetry,
  fallbackAction,
}: {
  error: unknown;
  onRetry?: () => void;
  /** Optional custom action that overrides the derived retry/reconnect button. */
  fallbackAction?: ReactNode;
}) {
  const friendly = describeError(error);
  const showRetry = friendly.kind === "retry" && onRetry;

  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-4 rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-14 text-center"
    >
      <div className="flex size-12 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
        <AlertTriangle className="size-6" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{friendly.title}</p>
        <p className="mx-auto max-w-md text-xs leading-5 text-muted-foreground">
          {friendly.message}
        </p>
      </div>
      {fallbackAction ?? (friendly.kind === "reconnect" ? (
        <Button
          variant="outline"
          render={
            <a href={githubOAuthUrl} />
          }
        >
          <ExternalLink className="size-4" />
          Reconnect GitHub
        </Button>
      ) : showRetry ? (
        <Button variant="outline" onClick={onRetry}>
          <RefreshCw className="size-4" />
          Try again
        </Button>
      ) : null)}
    </div>
  );
}
