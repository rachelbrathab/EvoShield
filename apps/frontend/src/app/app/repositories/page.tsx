"use client";

import { GitBranch, Plus } from "lucide-react";
import dynamic from "next/dynamic";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { deleteRepository, listRepositories, syncRepository } from "@/lib/repositories";
import {
  type Repository,
  type RepositoryListViewState,
} from "@/lib/repository";
import {
  hasActiveFilters,
  parseViewState,
  sortDefaultOrder,
  viewStateQuery,
  viewStateToParams,
} from "@/lib/repository-view";

import { DeleteRepositoryDialog } from "@/components/repositories/delete-repository-dialog";
import { RepositoryCard } from "@/components/repositories/repository-card";
import { RepositoryEmptyState } from "@/components/repositories/repository-empty-state";
import { RepositoryErrorState } from "@/components/repositories/repository-error-state";
import { RepositoryPagination } from "@/components/repositories/repository-pagination";
import { RepositoryToolbar } from "@/components/repositories/repository-toolbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

// The import dialog bundles the GitHub browsing flow (list + debounce + OAuth
// gate), so it is lazy-loaded and only fetched when first needed.
const ImportRepositoryDialog = dynamic(
  () =>
    import("@/components/repositories/import-repository-dialog").then(
      (module) => module.ImportRepositoryDialog,
    ),
  {
    ssr: false,
    loading: () => (
      <Button disabled>
        <Plus className="size-4" />
        Import repository
      </Button>
    ),
  },
);

const SEARCH_DEBOUNCE_MS = 350;

export default function RepositoriesPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <RepositoriesContent />
    </Suspense>
  );
}

function RepositoriesContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // View state is seeded once from the URL; every mutation flows through
  // `updateView`, which keeps the URL in sync (shareable, refresh-safe) and
  // resets the page when filters change. `viewRef` lets handlers read the
  // latest state without stale closures.
  const [initial] = useState(() => parseViewState(searchParams));
  const [view, setView] = useState<RepositoryListViewState>(initial);
  const viewRef = useRef(view);

  const [searchInput, setSearchInput] = useState(initial.q);

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<Repository | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestSeq = useRef(0);

  const updateView = useCallback(
    (change: Partial<RepositoryListViewState>) => {
      const current = viewRef.current;
      const next: RepositoryListViewState = { ...current, ...change };
      // Any change that isn't an explicit page jump resets to page 1, so
      // search/filter/sort/page-size edits always start from the top.
      if (!("page" in change)) next.page = 1;
      // Picking a new sort key snaps the direction to its natural default.
      if (change.sort && change.sort !== current.sort && change.order === undefined) {
        next.order = sortDefaultOrder(change.sort);
      }
      viewRef.current = next;
      setView(next);
      router.replace(`${pathname}${viewStateQuery(next)}`, { scroll: false });
    },
    [pathname, router],
  );

  // Debounced search: the input is local state; the debounced value lands in
  // the view state (and URL) 350ms after the user stops typing.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const trimmed = searchInput.trim();
      if (trimmed !== viewRef.current.q) updateView({ q: trimmed });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchInput, updateView]);

  // Back/forward restore the view state from the URL.
  useEffect(() => {
    const onPopState = () => {
      const next = parseViewState(new URLSearchParams(window.location.search));
      viewRef.current = next;
      setView(next);
      setSearchInput(next.q);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const listParams = useMemo(() => viewStateToParams(view), [view]);

  // Fetch whenever the view state changes. `.then/.catch/.finally` keeps
  // setState out of the synchronous effect body (react-hooks/set-state-in-effect);
  // requestSeq guards against out-of-order responses.
  useEffect(() => {
    let cancelled = false;
    const seq = ++requestSeq.current;
    listRepositories(listParams)
      .then((result) => {
        if (cancelled || seq !== requestSeq.current) return;
        // A URL like `?page=99` with few results returns an empty page while
        // total > 0 — snap back to the last real page instead of showing a
        // misleading "no repositories" state. Triggers one follow-up fetch.
        if (result.total > 0 && result.items.length === 0 && result.page > 1) {
          updateView({ page: Math.max(1, result.total_pages) });
          return;
        }
        setRepositories(result.items);
        setTotal(result.total);
        setTotalPages(result.total_pages);
        setError(null);
      })
      .catch((err) => {
        if (cancelled || seq !== requestSeq.current) return;
        setError(err);
      })
      .finally(() => {
        if (!cancelled && seq === requestSeq.current) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [listParams, updateView]);

  // Re-fetch from event handlers (retry, after import/sync/delete).
  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    try {
      const result = await listRepositories(viewStateToParams(viewRef.current));
      if (seq !== requestSeq.current) return;
      setRepositories(result.items);
      setTotal(result.total);
      setTotalPages(result.total_pages);
      setError(null);
    } catch (err) {
      if (seq !== requestSeq.current) return;
      setError(err);
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  const handleSync = useCallback(
    async (repository: Repository) => {
      setSyncingId(repository.id);
      try {
        const result = await syncRepository(repository.id);
        if (result.warning) {
          toast.warning(result.warning);
        } else {
          toast.success(`Refreshed ${repository.full_name}`);
        }
        void load();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Sync failed");
      } finally {
        setSyncingId(null);
      }
    },
    [load],
  );

  const handleDelete = useCallback(
    async (repository: Repository) => {
      try {
        await deleteRepository(repository.id);
        toast.success(`Removed ${repository.full_name}`);
        setToDelete(null);
        void load();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Delete failed");
      }
    },
    [load],
  );

  const handleImported = useCallback(() => void load(), [load]);

  const clearFilters = useCallback(() => {
    setSearchInput("");
    updateView({
      q: "",
      language: "",
      visibility: "",
      status: "",
      imported: "",
      archived: "",
      disabled: "",
    });
  }, [updateView]);

  const filtersActive = hasActiveFilters(view);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      {/* Header */}
      <section className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-foreground">
            <GitBranch className="size-5 text-primary" aria-hidden />
            Repositories
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {loading
              ? "Loading…"
              : filtersActive
                ? `${total} ${total === 1 ? "match" : "matches"} for the current filters`
                : `${total} tracked ${total === 1 ? "repository" : "repositories"}`}{" "}
            — metadata is synced from GitHub, nothing is scanned yet.
          </p>
        </div>
        <ImportRepositoryDialog tracked={repositories} onImported={handleImported} />
      </section>

      {/* Toolbar */}
      <RepositoryToolbar
        view={view}
        searchInput={searchInput}
        onSearchInputChange={setSearchInput}
        onChange={updateView}
        onClearFilters={clearFilters}
      />

      {/* Body */}
      {loading ? (
        <RepositoryGridSkeleton />
      ) : error ? (
        <RepositoryErrorState error={error} onRetry={() => void load()} />
      ) : repositories.length === 0 ? (
        filtersActive ? (
          <RepositoryEmptyState
            icon={GitBranch}
            title="No repositories match your filters"
            message="Try removing a filter or clearing the search to see all your repositories."
            action={
              <Button variant="outline" onClick={clearFilters}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <RepositoryEmptyState
            icon={GitBranch}
            title="No repositories yet"
            message="Import a GitHub repository to start tracking its metadata and prepare for supply chain analysis."
            action={<ImportRepositoryDialog tracked={[]} onImported={handleImported} />}
          />
        )
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {repositories.map((repository) => (
              <RepositoryCard
                key={repository.id}
                repository={repository}
                syncing={syncingId === repository.id}
                searchQuery={view.q}
                onSync={handleSync}
                onDelete={setToDelete}
              />
            ))}
          </div>

          <RepositoryPagination
            page={view.page}
            totalPages={totalPages}
            total={total}
            pageSize={view.pageSize}
            onPageChange={(page) => updateView({ page })}
            onPageSizeChange={(pageSize) => updateView({ pageSize })}
          />
        </>
      )}

      <DeleteRepositoryDialog
        repository={toDelete}
        onOpenChange={(open) => {
          if (!open) setToDelete(null);
        }}
        onConfirm={handleDelete}
      />
    </div>
  );
}

function RepositoryGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="space-y-3 py-4">
            <div className="flex items-center gap-3">
              <Skeleton className="size-9 rounded-lg" />
              <div className="space-y-1.5">
                <Skeleton className="h-3.5 w-32" />
                <Skeleton className="h-3 w-24" />
              </div>
            </div>
            <Skeleton className="h-8 w-full" />
            <div className="flex gap-2">
              <Skeleton className="h-5 w-20 rounded-full" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-44" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-8 w-36" />
      </div>
      <Skeleton className="h-10 w-full" />
      <RepositoryGridSkeleton />
    </div>
  );
}
