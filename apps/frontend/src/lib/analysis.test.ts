import { describe, expect, it } from "vitest";

import {
  ANALYSIS_RUN_STATUS_META,
  ANALYSIS_RUN_STATUSES,
  isRunActive,
  isRunTerminal,
} from "@/lib/analysis";

describe("analysis run statuses", () => {
  it("defines all five lifecycle states in order", () => {
    expect(ANALYSIS_RUN_STATUSES).toEqual([
      "queued",
      "running",
      "completed",
      "failed",
      "cancelled",
    ]);
  });

  it("provides a label and dot color for every state", () => {
    for (const status of ANALYSIS_RUN_STATUSES) {
      const meta = ANALYSIS_RUN_STATUS_META[status];
      expect(meta.label).toBeTruthy();
      expect(meta.dot).toMatch(/^bg-/);
    }
  });
});

describe("isRunTerminal", () => {
  it("treats completed, failed and cancelled as terminal", () => {
    expect(isRunTerminal("completed")).toBe(true);
    expect(isRunTerminal("failed")).toBe(true);
    expect(isRunTerminal("cancelled")).toBe(true);
    expect(isRunTerminal("queued")).toBe(false);
    expect(isRunTerminal("running")).toBe(false);
  });
});

describe("isRunActive", () => {
  it("treats queued and running as active (cancellable)", () => {
    expect(isRunActive("queued")).toBe(true);
    expect(isRunActive("running")).toBe(true);
    expect(isRunActive("completed")).toBe(false);
    expect(isRunActive("failed")).toBe(false);
    expect(isRunActive("cancelled")).toBe(false);
  });
});
