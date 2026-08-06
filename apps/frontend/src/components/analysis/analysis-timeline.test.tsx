import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalysisTimeline } from "@/components/analysis/analysis-timeline";
import { makeAnalysisRun } from "@/test/fixtures";

describe("AnalysisTimeline", () => {
  it("renders the three lifecycle steps", () => {
    render(
      <AnalysisTimeline
        run={makeAnalysisRun({ status: "queued" })}
      />,
    );
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("labels the outcome as Failed for failed runs", () => {
    render(
      <AnalysisTimeline
        run={makeAnalysisRun({ status: "failed", completed_at: "2024-02-10T10:00:00Z" })}
      />,
    );
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("labels the outcome as Cancelled for cancelled runs", () => {
    render(
      <AnalysisTimeline
        run={makeAnalysisRun({ status: "cancelled", completed_at: "2024-02-10T10:00:00Z" })}
      />,
    );
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("shows Waiting for steps that have not started yet", () => {
    render(
      <AnalysisTimeline run={makeAnalysisRun({ status: "queued" })} />,
    );
    expect(screen.getAllByText("Waiting…").length).toBeGreaterThanOrEqual(2);
  });

  it("shows a spinner on the running step while active", () => {
    render(
      <AnalysisTimeline
        run={makeAnalysisRun({ status: "running", started_at: "2024-02-10T09:05:00Z" })}
      />,
    );
    const spinner = document.querySelector('[class*="animate-spin"]');
    expect(spinner).not.toBeNull();
  });
});
