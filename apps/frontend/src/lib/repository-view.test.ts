import { describe, expect, it } from "vitest";

import type { RepositoryListViewState } from "@/lib/repository";
import {
  DEFAULT_VIEW_STATE,
  encodeViewState,
  hasActiveFilters,
  parseViewState,
  sortDefaultOrder,
  viewStateQuery,
  viewStateToParams,
} from "@/lib/repository-view";

function params(query: string): URLSearchParams {
  return new URLSearchParams(query);
}

describe("parseViewState", () => {
  it("returns defaults for an empty query string", () => {
    expect(parseViewState(params(""))).toEqual(DEFAULT_VIEW_STATE);
  });

  it("parses every known parameter", () => {
    const state = parseViewState(
      params(
        "q=evoshield&lang=Python&vis=private&status=analyzed&imported=30d&" +
          "archived=true&disabled=false&sort=stars&order=asc&page=3&per=24",
      ),
    );
    expect(state).toEqual({
      q: "evoshield",
      language: "Python",
      visibility: "private",
      status: "analyzed",
      imported: "30d",
      archived: "true",
      disabled: "false",
      sort: "stars",
      order: "asc",
      page: 3,
      pageSize: 24,
    });
  });

  it("falls back to defaults for invalid values", () => {
    const state = parseViewState(
      params("vis=teal&status=bogus&sort=nope&order=sideways&page=-2&per=0"),
    );
    expect(state.visibility).toBe("");
    expect(state.status).toBe("");
    expect(state.sort).toBe("updated_at");
    expect(state.order).toBe("desc");
    expect(state.page).toBe(1);
    expect(state.pageSize).toBe(12);
  });

  it("clamps an out-of-range page size instead of passing it to the API", () => {
    // The backend caps page_size at 100 — a malformed `?per=999` must never
    // reach it and 422 the whole list.
    expect(parseViewState(params("per=999")).pageSize).toBe(12);
    expect(parseViewState(params("per=24")).pageSize).toBe(24);
    expect(parseViewState(params("per=13")).pageSize).toBe(12);
  });

  it("never throws on malformed values", () => {
    expect(() => parseViewState(params("page=abc&per=xyz&lang=%00"))).not.toThrow();
  });
});

describe("encodeViewState", () => {
  it("omits everything that equals the default state", () => {
    expect(encodeViewState(DEFAULT_VIEW_STATE).toString()).toBe("");
    expect(viewStateQuery(DEFAULT_VIEW_STATE)).toBe("");
  });

  it("round-trips a non-default state", () => {
    const state: RepositoryListViewState = {
      q: "core",
      language: "Go",
      visibility: "public",
      status: "not_analyzed",
      imported: "7d",
      archived: "false",
      disabled: "",
      sort: "name",
      order: "asc",
      page: 2,
      pageSize: 48,
    };
    const reparsed = parseViewState(encodeViewState(state));
    expect(reparsed).toEqual(state);
  });
});

describe("viewStateToParams", () => {
  it("drops empty values and maps tri-states to booleans", () => {
    const state: RepositoryListViewState = {
      ...DEFAULT_VIEW_STATE,
      language: "Rust",
      archived: "true",
      disabled: "false",
      visibility: "private",
    };
    const params = viewStateToParams(state);
    expect(params.language).toBe("Rust");
    expect(params.archived).toBe(true);
    expect(params.disabled).toBe(false);
    expect(params.visibility).toBe("private");
    expect(params.q).toBeUndefined();
    expect(params.imported_after).toBeUndefined();
    expect(params.analysis_status).toBeUndefined();
  });

  it("maps the imported range to an ISO timestamp", () => {
    const state: RepositoryListViewState = { ...DEFAULT_VIEW_STATE, imported: "30d" };
    const params = viewStateToParams(state);
    expect(params.imported_after).toBeDefined();
    expect(Number.isNaN(Date.parse(params.imported_after as string))).toBe(false);
  });
});

describe("hasActiveFilters", () => {
  it("is false for the default state", () => {
    expect(hasActiveFilters(DEFAULT_VIEW_STATE)).toBe(false);
  });

  it("is true when any search or filter is set", () => {
    expect(hasActiveFilters({ ...DEFAULT_VIEW_STATE, q: "x" })).toBe(true);
    expect(hasActiveFilters({ ...DEFAULT_VIEW_STATE, archived: "true" })).toBe(true);
    expect(hasActiveFilters({ ...DEFAULT_VIEW_STATE, sort: "stars" })).toBe(false);
  });
});

describe("sortDefaultOrder", () => {
  it("sorts textual keys ascending and numeric keys descending", () => {
    expect(sortDefaultOrder("name")).toBe("asc");
    expect(sortDefaultOrder("language")).toBe("asc");
    expect(sortDefaultOrder("stars")).toBe("desc");
    expect(sortDefaultOrder("updated_at")).toBe("desc");
  });
});
