import { GitBranch } from "lucide-react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RepositoryEmptyState } from "@/components/repositories/repository-empty-state";
import { Button } from "@/components/ui/button";

describe("RepositoryEmptyState", () => {
  it("renders title and message", () => {
    render(
      <RepositoryEmptyState
        icon={GitBranch}
        title="No repositories yet"
        message="Import a GitHub repository to get started."
      />,
    );
    expect(screen.getByText("No repositories yet")).toBeInTheDocument();
    expect(
      screen.getByText("Import a GitHub repository to get started."),
    ).toBeInTheDocument();
  });

  it("renders the action element when provided", () => {
    render(
      <RepositoryEmptyState
        icon={GitBranch}
        title="No repositories yet"
        message="Import a GitHub repository to get started."
        action={<Button>Import repository</Button>}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Import repository" }),
    ).toBeInTheDocument();
  });
});
