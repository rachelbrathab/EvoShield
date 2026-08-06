import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SearchHighlight } from "@/components/repositories/search-highlight";

describe("SearchHighlight", () => {
  function marks(container: HTMLElement): HTMLElement[] {
    return Array.from(container.querySelectorAll("mark"));
  }

  it("wraps matching text in a mark element", () => {
    const { container } = render(
      <SearchHighlight text="Evoshield Core" query="shield" />,
    );
    expect(marks(container).map((mark) => mark.textContent)).toEqual(["shield"]);
  });

  it("matches case-insensitively", () => {
    const { container } = render(
      <SearchHighlight text="Evoshield Core" query="EVO" />,
    );
    expect(marks(container).map((mark) => mark.textContent)).toEqual(["Evo"]);
  });

  it("renders plain text when the query is empty", () => {
    const { container } = render(<SearchHighlight text="Evoshield Core" query="" />);
    expect(marks(container)).toHaveLength(0);
    expect(screen.getByText("Evoshield Core")).toBeInTheDocument();
  });

  it("renders plain text when nothing matches", () => {
    const { container } = render(
      <SearchHighlight text="Evoshield Core" query="zzz" />,
    );
    expect(marks(container)).toHaveLength(0);
  });
});
