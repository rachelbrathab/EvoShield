/**
 * Friendly, code-aware error descriptions for the repository UI (Sprint 3B).
 *
 * The backend returns `{"error": {"code", "message"}}` (see `@/lib/api`).
 * Instead of showing raw messages, we map the known codes to human copy with
 * an actionable suggestion and a `kind` that drives what the state renders:
 *
 * - "retry"    → show a "Try again" button
 * - "reconnect" → show a "Reconnect GitHub" link
 * - "fatal"    → explain and offer to go back
 *
 * Unknown errors fall through to a generic message that still shows the
 * backend detail when one exists.
 */

import type { ApiError } from "@/lib/api";

export type ErrorKind = "retry" | "reconnect" | "fatal";

export type FriendlyError = {
  /** Code as returned by the backend (or "network_error"). */
  code: string;
  /** Short headline, e.g. "GitHub rate limit reached". */
  title: string;
  /** One or two sentences explaining what happened and what to do. */
  message: string;
  /** What action the error state should offer. */
  kind: ErrorKind;
};

function fromErrorCode(code: string): FriendlyError | null {
  switch (code) {
    case "github_rate_limited":
      return {
        code,
        title: "GitHub rate limit reached",
        message:
          "GitHub is throttling API requests right now. Wait a minute or two, then try again.",
        kind: "retry",
      };
    case "github_token_invalid":
      return {
        code,
        title: "GitHub connection expired",
        message:
          "EvoShield can no longer reach your GitHub account. Reconnect GitHub to refresh repository metadata.",
        kind: "reconnect",
      };
    case "github_not_connected":
      return {
        code,
        title: "GitHub not connected",
        message:
          "Connect your GitHub account to browse and import repositories into EvoShield.",
        kind: "reconnect",
      };
    case "github_forbidden":
      return {
        code,
        title: "Access to GitHub was denied",
        message:
          "The GitHub token is missing the permissions EvoShield needs. Reconnect GitHub and accept the requested scopes.",
        kind: "reconnect",
      };
    case "not_found":
      return {
        code,
        title: "Repository not found",
        message:
          "This repository no longer exists or is no longer accessible. It may have been deleted or made private.",
        kind: "fatal",
      };
    case "network_error":
      return {
        code,
        title: "Can't reach the EvoShield API",
        message:
          "The connection to the backend failed. Check that the API server is running and your network is up.",
        kind: "retry",
      };
    default:
      return null;
  }
}

/** Map any thrown value (ApiError, Error, unknown) to a `FriendlyError`. */
export function describeError(error: unknown): FriendlyError {
  if (error instanceof Error) {
    const apiError = error as ApiError;
    if (typeof apiError.code === "string") {
      const mapped = fromErrorCode(apiError.code);
      if (mapped) return mapped;
      return {
        code: apiError.code,
        title: "Something went wrong",
        message: apiError.message || "An unexpected error occurred.",
        kind: apiError.status === 401 || apiError.status === 403 ? "reconnect" : "retry",
      };
    }
  }
  return {
    code: "unknown_error",
    title: "Something went wrong",
    message: "An unexpected error occurred while loading this view.",
    kind: "retry",
  };
}
