"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { PAGE_SIZE_OPTIONS } from "@/lib/repository-view";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";

/**
 * Page numbers to render with ellipses, e.g. for 10 pages at page 7:
 * `[1, "…", 6, 7, 8, "…", 10]`. Pure so it can be unit-tested.
 */
export function pageNumberList(page: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const pages = new Set<number>([1, totalPages]);
  for (let offset = -1; offset <= 1; offset += 1) {
    const candidate = page + offset;
    if (candidate >= 1 && candidate <= totalPages) pages.add(candidate);
  }
  const sorted = [...pages].sort((a, b) => a - b);
  const result: Array<number | "ellipsis"> = [];
  let previous = 0;
  for (const current of sorted) {
    if (current - previous > 1) result.push("ellipsis");
    result.push(current);
    previous = current;
  }
  return result;
}

export function RepositoryPagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  onPageSizeChange,
  noun = "repository",
  nounPlural = "repositories",
  showPageSize = true,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  /** Singular label for the count summary, e.g. "run" (default "repository"). */
  noun?: string;
  /** Plural label, e.g. "runs" (default "repositories"). */
  nounPlural?: string;
  /** Show the results-per-page selector (default true). */
  showPageSize?: boolean;
}) {
  if (totalPages <= 1) return null;

  const pages = pageNumberList(page, totalPages);
  const selectClass =
    "h-8 rounded-lg border border-input bg-transparent px-2 text-xs text-foreground transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

  return (
    <nav
      aria-label="Repositories pagination"
      className="flex flex-col items-center justify-between gap-3 border-t border-border/60 pt-4 sm:flex-row"
    >
      <p className="text-xs text-muted-foreground">
        Showing <span className="font-medium text-foreground">{total}</span>{" "}
        {total === 1 ? noun : nounPlural} · page{" "}
        <span className="font-medium text-foreground">{page}</span> of{" "}
        <span className="font-medium text-foreground">{totalPages}</span>
      </p>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="size-3.5" />
          <span className="sr-only sm:not-sr-only">Previous</span>
        </Button>

        <div className="flex items-center gap-1">
          {pages.map((item, index) =>
            item === "ellipsis" ? (
              <span
                key={`ellipsis-${index}`}
                aria-hidden
                className="px-1 text-xs text-muted-foreground"
              >
                …
              </span>
            ) : (
              <Button
                key={item}
                variant={item === page ? "default" : "ghost"}
                size="xs"
                aria-current={item === page ? "page" : undefined}
                onClick={() => onPageChange(item)}
              >
                {item}
              </Button>
            ),
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          aria-label="Next page"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          <span className="sr-only sm:not-sr-only">Next</span>
          <ChevronRight className="size-3.5" />
        </Button>

        {showPageSize ? (
          <label className="ml-2 flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="sr-only">Results per page</span>
            <select
              className={cn(selectClass, "h-8")}
              value={pageSize}
              aria-label="Results per page"
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size} / page
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
    </nav>
  );
}
