"use client";

import { ArrowDownWideNarrow, ArrowUpNarrowWide, Search, X } from "lucide-react";

import {
  ANALYSIS_STATUSES,
  ANALYSIS_STATUS_META,
  type RepositoryListViewState,
  type RepositorySortKey,
} from "@/lib/repository";
import { hasActiveFilters, IMPORTED_OPTIONS, SORT_OPTIONS } from "@/lib/repository-view";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const LANGUAGE_OPTIONS = [
  "Python",
  "TypeScript",
  "JavaScript",
  "Go",
  "Rust",
  "Java",
  "C++",
  "C",
  "C#",
  "Ruby",
  "PHP",
  "Swift",
  "Kotlin",
  "Shell",
  "HTML",
  "CSS",
];

export type ToolbarChange = Partial<Omit<RepositoryListViewState, "q">>;

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm text-foreground transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50";

/**
 * Search + filters + sort for the repository list. The debounce of the search
 * box is owned by the parent (it also drives the URL), so the input is fully
 * controlled. Every filter change flows through `onChange` with the page
 * reset handled by the parent's unified update helper.
 */
export function RepositoryToolbar({
  view,
  searchInput,
  onSearchInputChange,
  onChange,
  onClearFilters,
}: {
  view: RepositoryListViewState;
  searchInput: string;
  onSearchInputChange: (value: string) => void;
  onChange: (change: ToolbarChange) => void;
  onClearFilters: () => void;
}) {
  const filtersActive = hasActiveFilters(view);

  return (
    <section className="space-y-2.5" aria-label="Repository filters">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-8"
          placeholder="Search name, owner or description…"
          value={searchInput}
          onChange={(event) => onSearchInputChange(event.target.value)}
          aria-label="Search repositories"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          className={selectClass}
          value={view.language}
          onChange={(event) => onChange({ language: event.target.value })}
          aria-label="Filter by language"
        >
          <option value="">All languages</option>
          {LANGUAGE_OPTIONS.map((lang) => (
            <option key={lang} value={lang}>
              {lang}
            </option>
          ))}
        </select>

        <select
          className={selectClass}
          value={view.visibility}
          onChange={(event) =>
            onChange({ visibility: event.target.value as RepositoryListViewState["visibility"] })
          }
          aria-label="Filter by visibility"
        >
          <option value="">All visibilities</option>
          <option value="public">Public</option>
          <option value="private">Private</option>
        </select>

        <select
          className={selectClass}
          value={view.status}
          onChange={(event) =>
            onChange({ status: event.target.value as RepositoryListViewState["status"] })
          }
          aria-label="Filter by analysis status"
        >
          <option value="">All statuses</option>
          {ANALYSIS_STATUSES.map((value) => (
            <option key={value} value={value}>
              {ANALYSIS_STATUS_META[value].label}
            </option>
          ))}
        </select>

        <select
          className={selectClass}
          value={view.imported}
          onChange={(event) =>
            onChange({ imported: event.target.value as RepositoryListViewState["imported"] })
          }
          aria-label="Filter by import recency"
        >
          {IMPORTED_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              Imported: {option.label.toLowerCase()}
            </option>
          ))}
        </select>

        <select
          className={selectClass}
          value={view.archived}
          onChange={(event) =>
            onChange({ archived: event.target.value as RepositoryListViewState["archived"] })
          }
          aria-label="Filter by archived state"
        >
          <option value="">Archived: any</option>
          <option value="true">Archived</option>
          <option value="false">Not archived</option>
        </select>

        <select
          className={selectClass}
          value={view.disabled}
          onChange={(event) =>
            onChange({ disabled: event.target.value as RepositoryListViewState["disabled"] })
          }
          aria-label="Filter by disabled state"
        >
          <option value="">Disabled: any</option>
          <option value="true">Disabled</option>
          <option value="false">Not disabled</option>
        </select>

        <div className="ml-auto flex items-center gap-1.5">
          <select
            className={selectClass}
            value={view.sort}
            onChange={(event) =>
              onChange({ sort: event.target.value as RepositorySortKey })
            }
            aria-label="Sort repositories"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                Sort: {option.label}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={view.order === "desc" ? "Sort descending — switch to ascending" : "Sort ascending — switch to descending"}
            title={view.order === "desc" ? "Descending" : "Ascending"}
            onClick={() => onChange({ order: view.order === "desc" ? "asc" : "desc" })}
          >
            {view.order === "desc" ? (
              <ArrowDownWideNarrow className="size-3.5" />
            ) : (
              <ArrowUpNarrowWide className="size-3.5" />
            )}
          </Button>
        </div>

        {filtersActive ? (
          <Button variant="ghost" size="sm" onClick={onClearFilters}>
            <X className="size-3.5" />
            Clear filters
          </Button>
        ) : null}
      </div>
    </section>
  );
}
