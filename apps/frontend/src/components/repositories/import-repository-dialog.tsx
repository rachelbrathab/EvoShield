"use client";

import { GitBranch, Loader2, Lock, Plus, RefreshCw, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { githubOAuthUrl } from "@/lib/api";
import { compactNumber, relativeTime } from "@/lib/format";
import {
  type GitHubRepositoryCandidate,
  type Repository,
} from "@/lib/repository";
import {
  importRepository,
  isTracked,
  searchGitHubRepositories,
} from "@/lib/repositories";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogPopup,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

type ImportRepositoryDialogProps = {
  tracked: Repository[];
  onImported: () => void;
};

export function ImportRepositoryDialog({
  tracked,
  onImported,
}: ImportRepositoryDialogProps) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"browse" | "by-name">("browse");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [candidates, setCandidates] = useState<GitHubRepositoryCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notConnected, setNotConnected] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [manualName, setManualName] = useState("");
  const [manualImporting, setManualImporting] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce the browse search box. setLoading inside the timeout (async)
  // so the search re-fetch shows skeletons without a synchronous setState
  // in the effect body (react-hooks/set-state-in-effect).
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(query);
      setLoading(true);
    }, 350);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Fetch the candidate list when the dialog opens or the (debounced) query
  // changes. `.then/.catch/.finally` keeps setState out of the synchronous
  // effect body (react-hooks/set-state-in-effect); the initial `loading=true`
  // and the debounce's setLoading(true) cover the skeleton states.
  useEffect(() => {
    if (!(open && mode === "browse")) return;
    let cancelled = false;
    searchGitHubRepositories({ q: debouncedQuery, per_page: 50 })
      .then((page) => {
        if (cancelled) return;
        setCandidates(page.items);
        setError(null);
        setNotConnected(false);
      })
      .catch((err) => {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "Could not load repositories";
        if (
          err instanceof Error &&
          "code" in err &&
          (err as { code?: string }).code === "github_not_connected"
        ) {
          setNotConnected(true);
        } else {
          setError(message);
        }
        setCandidates([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, mode, debouncedQuery]);

  async function handleImport(candidate: GitHubRepositoryCandidate) {
    setImporting(candidate.provider_repo_id);
    try {
      const result = await importRepository(candidate.full_name);
      toast.success(
        result.was_already_imported
          ? `${candidate.full_name} was already tracked — metadata refreshed.`
          : `Imported ${candidate.full_name}.`,
      );
      onImported();
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(null);
    }
  }

  async function handleManualImport(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = manualName.trim();
    if (!name) return;
    setManualImporting(true);
    try {
      const result = await importRepository(name);
      toast.success(
        result.was_already_imported
          ? `${name} was already tracked — metadata refreshed.`
          : `Imported ${name}.`,
      );
      onImported();
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Import failed");
    } finally {
      setManualImporting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            Import repository
          </Button>
        }
      />
      <DialogPopup className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import a repository</DialogTitle>
          <DialogDescription>
            Track a GitHub repository in EvoShield. Metadata is fetched from
            GitHub — no code is cloned or scanned yet.
          </DialogDescription>
        </DialogHeader>

        {/* Mode toggle */}
        <div className="mt-4 grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">
          {(["browse", "by-name"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === m
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {m === "browse" ? "Browse GitHub" : "Import by name"}
            </button>
          ))}
        </div>

        {mode === "browse" ? (
          <div className="mt-4 space-y-3">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-8"
                placeholder="Search your GitHub repositories…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>

            {notConnected ? (
              <div className="rounded-lg border border-border bg-muted/40 p-5 text-center">
                <GitBranch className="mx-auto size-6 text-muted-foreground" />
                <p className="mt-2 text-sm font-medium text-foreground">
                  Connect your GitHub account
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  You need to authorize EvoShield to list and import your
                  repositories.
                </p>
                <Button className="mt-4" onClick={() => { window.location.href = githubOAuthUrl; }}>
                  Continue with GitHub
                </Button>
              </div>
            ) : (
              <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
                {loading ? (
                  <div className="space-y-1.5">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-14 w-full rounded-lg" />
                    ))}
                  </div>
                ) : error ? (
                  <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                    {error}
                  </p>
                ) : candidates.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    No GitHub repositories found
                    {debouncedQuery ? ` matching “${debouncedQuery}”` : ""}.
                  </p>
                ) : (
                  candidates.map((candidate) => {
                    const alreadyTracked = isTracked(candidate, tracked);
                    return (
                      <div
                        key={candidate.provider_repo_id}
                        className="flex items-center gap-3 rounded-lg border border-border bg-card p-2.5 transition-colors hover:border-primary/40"
                      >
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                          <GitBranch className="size-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-foreground">
                            {candidate.full_name}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">
                            {candidate.description ||
                              `${candidate.language ?? "Unknown language"} · ${compactNumber(candidate.stars)} stars`}
                            {candidate.is_private ? " · Private" : ""}
                            {" · "}
                            {relativeTime(candidate.pushed_at)}
                          </p>
                        </div>
                        {candidate.is_private ? (
                          <Lock className="size-3.5 shrink-0 text-muted-foreground" />
                        ) : null}
                        <Button
                          size="sm"
                          variant={alreadyTracked ? "outline" : "default"}
                          disabled={importing !== null}
                          onClick={() => void handleImport(candidate)}
                        >
                          {importing === candidate.provider_repo_id ? (
                            <Loader2 className="size-3.5 animate-spin" />
                          ) : alreadyTracked ? (
                            <RefreshCw className="size-3.5" />
                          ) : (
                            <Plus className="size-3.5" />
                          )}
                          {alreadyTracked ? "Refresh" : "Import"}
                        </Button>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={handleManualImport} className="mt-4 space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="repo-full-name">Owner / repository</Label>
              <Input
                id="repo-full-name"
                placeholder="octocat/Hello-World"
                value={manualName}
                onChange={(event) => setManualName(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Paste the GitHub URL or the <code>owner/name</code> pair.
              </p>
            </div>
            <DialogFooter>
              <Button
                type="submit"
                disabled={manualImporting || !manualName.trim()}
              >
                {manualImporting ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Plus className="size-4" />
                )}
                Import repository
              </Button>
            </DialogFooter>
          </form>
        )}

        <DialogFooter className="mt-5">
          <DialogClose
            render={<Button variant="ghost">Cancel</Button>}
          />
        </DialogFooter>
      </DialogPopup>
    </Dialog>
  );
}
