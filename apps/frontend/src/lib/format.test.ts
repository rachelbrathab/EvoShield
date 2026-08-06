import { describe, expect, it } from "vitest";

import { compactNumber, formatDate, formatSizeKb, relativeTime } from "@/lib/format";

describe("compactNumber", () => {
  it("formats small numbers verbatim", () => {
    expect(compactNumber(42)).toBe("42");
  });

  it("compacts thousands", () => {
    // ICU may emit the suffix as "K" or "k" depending on the runtime.
    expect(compactNumber(12_500)).toMatch(/^12\.5[Kk]$/);
  });

  it("compacts millions", () => {
    expect(compactNumber(2_400_000)).toBe("2.4M");
  });

  it("returns an en dash for nullish input", () => {
    expect(compactNumber(null)).toBe("–");
    expect(compactNumber(undefined)).toBe("–");
  });
});

describe("formatSizeKb", () => {
  it("formats KiB as KB", () => {
    expect(formatSizeKb(512)).toBe("512 KB");
  });

  it("converts to MB above 1024 KiB", () => {
    expect(formatSizeKb(2048)).toBe("2.0 MB");
  });
});

describe("relativeTime", () => {
  it("returns Never for missing values", () => {
    expect(relativeTime(null)).toBe("Never");
    expect(relativeTime(undefined)).toBe("Never");
    expect(relativeTime("not-a-date")).toBe("Never");
  });

  it("returns a human phrase for a recent date", () => {
    expect(relativeTime(new Date().toISOString())).toBe("just now");
  });

  it("returns a past-relative phrase for an old date", () => {
    const old = new Date(Date.now() - 2 * 365 * 24 * 60 * 60 * 1000).toISOString();
    expect(relativeTime(old)).toContain("year");
  });
});

describe("formatDate", () => {
  it("formats an ISO date", () => {
    expect(formatDate("2024-01-15T10:00:00Z")).toBe("Jan 15, 2024");
  });

  it("returns Never for missing values", () => {
    expect(formatDate(null)).toBe("Never");
    expect(formatDate("")).toBe("Never");
  });
});
