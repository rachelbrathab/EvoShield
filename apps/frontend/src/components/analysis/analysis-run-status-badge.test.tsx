import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalysisRunStatusBadge } from "@/components/analysis/analysis-run-status-badge";

describe("AnalysisRunStatusBadge", () => {
  it.each([
    ["queued", "Queued"],
    ["running", "Running"],
    ["completed", "Completed"],
    ["failed", "Failed"],
    ["cancelled", "Cancelled"],
  ] as const)("renders the %s label", (status, label) => {
    render(<AnalysisRunStatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
