import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, githubOAuthUrl } from "@/lib/api";

import { RepositoryErrorState } from "@/components/repositories/repository-error-state";

describe("RepositoryErrorState", () => {
  it("shows a retry button for rate limits and triggers onRetry", () => {
    const onRetry = vi.fn();
    render(
      <RepositoryErrorState
        error={new ApiError(429, "github_rate_limited", "rate limit hit")}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText(/rate limit/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows a reconnect link when GitHub is not connected", () => {
    render(
      <RepositoryErrorState
        error={new ApiError(401, "github_not_connected", "not connected")}
      />,
    );
    const link = screen.getByRole("link", { name: "Reconnect GitHub" });
    expect(link).toHaveAttribute("href", githubOAuthUrl);
  });

  it("renders a fallback action when supplied", () => {
    render(
      <RepositoryErrorState
        error={new ApiError(404, "not_found", "gone")}
        fallbackAction={<button>Go back</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Go back" })).toBeInTheDocument();
  });

  it("marks the region as an alert", () => {
    render(
      <RepositoryErrorState error={new Error("boom")} />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
