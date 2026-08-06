/**
 * Repository list view-state ⇄ URL query-string mapping (Sprint 3B).
 *
 * The list toolbar (search / filters / sort / pagination) is a single
 * `RepositoryListViewState` that serializes into the URL, so refresh, share
 * and back/forward all restore the exact view. Pure functions — no React —
 * so they are trivially unit-testable.
 */

import {
  ANALYSIS_STATUSES,
  importedAfterIso,
  type ImportedRange,
  type RepositoryListParams,
  type RepositoryListViewState,
  type RepositorySortKey,
} from "@/lib/repository";

/** Default view state — what a fresh `/app/repositories` shows. */
export const DEFAULT_VIEW_STATE: RepositoryListViewState = {
  q: "",
  language: "",
  visibility: "",
  status: "",
  imported: "",
  archived: "",
  disabled: "",
  sort: "updated_at",
  order: "desc",
  page: 1,
  pageSize: 12,
};

export const PAGE_SIZE_OPTIONS = [12, 24, 48] as const;

/** Sort keys the API accepts, in toolbar order. */
export const SORT_OPTIONS: Array<{ value: RepositorySortKey; label: string }> = [
  { value: "updated_at", label: "Recently updated" },
  { value: "name", label: "Name" },
  { value: "stars", label: "Most stars" },
  { value: "forks", label: "Most forks" },
  { value: "language", label: "Language" },
  { value: "size_kb", label: "Largest size" },
  { value: "pushed_at", label: "Last push" },
  { value: "created_at", label: "Recently imported" },
];

/** "Imported" recency presets offered by the toolbar. */
export const IMPORTED_OPTIONS: Array<{ value: ImportedRange; label: string }> = [
  { value: "", label: "Any time" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
];

const VISIBILITY_VALUES: RepositoryListViewState["visibility"][] = ["", "public", "private"];
const STATUS_VALUES: RepositoryListViewState["status"][] = ["", ...ANALYSIS_STATUSES];
const TRI_STATE_VALUES: RepositoryListViewState["archived"][] = ["", "true", "false"];
const ORDER_VALUES: RepositoryListViewState["order"][] = ["asc", "desc"];
const IMPORTED_VALUES: ImportedRange[] = ["", "7d", "30d", "90d"];
const SORT_VALUES = SORT_OPTIONS.map((option) => option.value);

/** Sensible sort direction when the user picks a new sort key. */
export function sortDefaultOrder(sort: RepositorySortKey): "asc" | "desc" {
  return sort === "name" || sort === "language" ? "asc" : "desc";
}

function oneOf<T>(value: string | null, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function parsePositiveInt(value: string | null, fallback: number): number {
  const parsed = value ? Number.parseInt(value, 10) : NaN;
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : fallback;
}

/**
 * Parse a `URLSearchParams` (from the location) into a valid view state.
 * Unknown or malformed values fall back to defaults — never throw.
 */
export function parseViewState(searchParams: URLSearchParams): RepositoryListViewState {
  const rawOrder = oneOf(searchParams.get("order"), ORDER_VALUES, "desc");
  const rawPageSize = parsePositiveInt(
    searchParams.get("per"),
    DEFAULT_VIEW_STATE.pageSize,
  );
  return {
    q: (searchParams.get("q") ?? "").slice(0, 256),
    language: (searchParams.get("lang") ?? "").slice(0, 64),
    visibility: oneOf(searchParams.get("vis"), VISIBILITY_VALUES, ""),
    status: oneOf(searchParams.get("status"), STATUS_VALUES, ""),
    imported: oneOf(searchParams.get("imported"), IMPORTED_VALUES, ""),
    archived: oneOf(searchParams.get("archived"), TRI_STATE_VALUES, ""),
    disabled: oneOf(searchParams.get("disabled"), TRI_STATE_VALUES, ""),
    sort: oneOf(searchParams.get("sort"), SORT_VALUES, DEFAULT_VIEW_STATE.sort),
    order: rawOrder,
    page: parsePositiveInt(searchParams.get("page"), 1),
    // Clamp the page size to the known options — a malformed `?per=999` must
    // not reach the API (the backend caps at 100 and would 422 the list).
    pageSize: (PAGE_SIZE_OPTIONS as readonly number[]).includes(rawPageSize)
      ? rawPageSize
      : DEFAULT_VIEW_STATE.pageSize,
  };
}

/**
 * Serialize a view state to query params, omitting values that equal the
 * defaults (keeps URLs short and stable for share/refresh).
 */
export function encodeViewState(state: RepositoryListViewState): URLSearchParams {
  const params = new URLSearchParams();
  const set = (key: string, value: string) => {
    if (value) params.set(key, value);
  };

  set("q", state.q);
  set("lang", state.language);
  set("vis", state.visibility);
  set("status", state.status);
  set("imported", state.imported);
  set("archived", state.archived);
  set("disabled", state.disabled);
  if (state.sort !== DEFAULT_VIEW_STATE.sort) set("sort", state.sort);
  if (state.order !== DEFAULT_VIEW_STATE.order) set("order", state.order);
  if (state.page !== 1) set("page", String(state.page));
  if (state.pageSize !== DEFAULT_VIEW_STATE.pageSize) set("per", String(state.pageSize));
  return params;
}

/** Query-string for the URL, or "" when the state is the default. */
export function viewStateQuery(state: RepositoryListViewState): string {
  const params = encodeViewState(state);
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** Whether any search/filter (not sort/page) is active — drives the "clear" button. */
export function hasActiveFilters(state: RepositoryListViewState): boolean {
  return Boolean(
    state.q || state.language || state.visibility || state.status ||
      state.imported || state.archived || state.disabled,
  );
}

/** Map the view state to the API's `RepositoryListParams` contract. */
export function viewStateToParams(state: RepositoryListViewState): RepositoryListParams {
  const params: RepositoryListParams = {
    page: state.page,
    page_size: state.pageSize,
    q: state.q || undefined,
    language: state.language || undefined,
    visibility: state.visibility || undefined,
    analysis_status: state.status || undefined,
    sort: state.sort,
    order: state.order,
  };
  if (state.archived) params.archived = state.archived === "true";
  if (state.disabled) params.disabled = state.disabled === "true";
  if (state.imported) {
    params.imported_after = importedAfterIso(state.imported);
  }
  return params;
}
