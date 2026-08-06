import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  pageNumberList,
  RepositoryPagination,
} from "@/components/repositories/repository-pagination";

describe("pageNumberList", () => {
  it("lists all pages when totalPages is small", () => {
    expect(pageNumberList(1, 3)).toEqual([1, 2, 3]);
  });

  it("windows around the current page with ellipses", () => {
    expect(pageNumberList(7, 10)).toEqual([1, "ellipsis", 6, 7, 8, "ellipsis", 10]);
  });

  it("keeps the first and last pages visible", () => {
    expect(pageNumberList(1, 20)).toEqual([1, 2, "ellipsis", 20]);
    expect(pageNumberList(20, 20)).toEqual([1, "ellipsis", 19, 20]);
  });
});

describe("RepositoryPagination", () => {
  it("renders nothing for a single page", () => {
    const { container } = render(
      <RepositoryPagination
        page={1}
        totalPages={1}
        total={3}
        pageSize={12}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("disables Previous on page one and marks the current page", () => {
    render(
      <RepositoryPagination
        page={2}
        totalPages={5}
        total={50}
        pageSize={12}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
      />,
    );
    const current = screen.getByRole("button", { name: "2" });
    expect(current).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled();
  });

  it("calls onPageChange when a page number is clicked", () => {
    const onPageChange = vi.fn();
    render(
      <RepositoryPagination
        page={1}
        totalPages={4}
        total={40}
        pageSize={12}
        onPageChange={onPageChange}
        onPageSizeChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("calls onPageSizeChange when the selector changes", () => {
    const onPageSizeChange = vi.fn();
    render(
      <RepositoryPagination
        page={1}
        totalPages={4}
        total={40}
        pageSize={12}
        onPageChange={vi.fn()}
        onPageSizeChange={onPageSizeChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("Results per page"), {
      target: { value: "24" },
    });
    expect(onPageSizeChange).toHaveBeenCalledWith(24);
  });
});
