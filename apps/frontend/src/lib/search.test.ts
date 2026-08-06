import { describe, expect, it } from "vitest";

import { highlightSegments } from "@/lib/search";

describe("highlightSegments", () => {
  it("returns a single plain segment for an empty query", () => {
    expect(highlightSegments("Hello World", "")).toEqual([
      { text: "Hello World", highlighted: false },
    ]);
    expect(highlightSegments("Hello World", "   ")).toEqual([
      { text: "Hello World", highlighted: false },
    ]);
  });

  it("returns a single plain segment for an empty text", () => {
    expect(highlightSegments("", "hello")).toEqual([
      { text: "", highlighted: false },
    ]);
  });

  it("marks case-insensitive matches", () => {
    expect(highlightSegments("Hello World", "ell")).toEqual([
      { text: "H", highlighted: false },
      { text: "ell", highlighted: true },
      { text: "o World", highlighted: false },
    ]);
  });

  it("marks every occurrence of the query", () => {
    expect(highlightSegments("banana", "an")).toEqual([
      { text: "b", highlighted: false },
      { text: "an", highlighted: true },
      { text: "an", highlighted: true },
      { text: "a", highlighted: false },
    ]);
  });

  it("handles a query longer than the text gracefully", () => {
    expect(highlightSegments("hi", "hello")).toEqual([
      { text: "hi", highlighted: false },
    ]);
  });

  it("joins matched segments back to the original text", () => {
    const segments = highlightSegments("Evoshield Core", "shield");
    expect(segments.map((segment) => segment.text).join("")).toBe("Evoshield Core");
  });
});
