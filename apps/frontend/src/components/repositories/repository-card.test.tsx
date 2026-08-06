import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { makeRepository } from "@/test/fixtures";

import { RepositoryCard } from "@/components/repositories/repository-card";

describe("RepositoryCard", () => {
  const handlers = {
    onSync: vi.fn(),
    onDelete: vi.fn(),
  };

  it("renders name, owner, description and language", () => {
    const repository = makeRepository();
    render(
      <RepositoryCard
        repository={repository}
        syncing={false}
        onSync={handlers.onSync}
        onDelete={handlers.onDelete}
      />,
    );

    expect(screen.getByRole("link", { name: "evoshield" })).toHaveAttribute(
      "href",
      "/app/repositories/repo-id-1",
    );
    expect(screen.getByText("octocat")).toBeInTheDocument();
    expect(screen.getByText(repository.description!)).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("shows topic chips and a +n overflow chip", () => {
    const repository = makeRepository({
      topics: ["security", "devsecops", "python", "supply-chain", "scanner"],
    });
    render(
      <RepositoryCard
        repository={repository}
        syncing={false}
        onSync={handlers.onSync}
        onDelete={handlers.onDelete}
      />,
    );

    expect(screen.getByText("security")).toBeInTheDocument();
    expect(screen.getByText("+2 more")).toBeInTheDocument();
  });

  it("renders the analysis status label", () => {
    render(
      <RepositoryCard
        repository={makeRepository({ analysis_status: "analyzed" })}
        syncing={false}
        onSync={handlers.onSync}
        onDelete={handlers.onDelete}
      />,
    );
    expect(screen.getByText("Analyzed")).toBeInTheDocument();
  });

  it("shows the compact star count", () => {
    render(
      <RepositoryCard
        repository={makeRepository({ stars: 12_500 })}
        syncing={false}
        onSync={handlers.onSync}
        onDelete={handlers.onDelete}
      />,
    );
    // ICU may render the compact suffix as "K" or "k" depending on the runtime.
    expect(screen.getByText((content) => /12\.5/i.test(content))).toBeInTheDocument();
  });

  it("marks the private badge for private repositories", () => {
    render(
      <RepositoryCard
        repository={makeRepository({ is_private: true })}
        syncing={false}
        onSync={handlers.onSync}
        onDelete={handlers.onDelete}
      />,
    );
    expect(screen.getByText("Private")).toBeInTheDocument();
  });
});
