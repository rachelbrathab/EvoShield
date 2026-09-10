"use client";

import {
  BookOpen,
  Eye,
  ExternalLink,
  GitBranch,
  GitFork,
  Loader2,
  Lock,
  MoreHorizontal,
  RefreshCw,
  Star,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { memo } from "react";

import { compactNumber, languageDotClass, relativeTime } from "@/lib/format";
import {
  repositoryName,
  repositoryOwner,
  type Repository,
} from "@/lib/repository";

import { AnalysisStatusBadge } from "@/components/repositories/analysis-status-badge";
import { SearchHighlight } from "@/components/repositories/search-highlight";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const MAX_VISIBLE_TOPICS = 3;

type RepositoryCardProps = {
  repository: Repository;
  syncing: boolean;
  /** Active search term — highlights matching name/owner/description. */
  searchQuery?: string;
  onSync: (repository: Repository) => void;
  onDelete: (repository: Repository) => void;
};

/**
 * Repository card. `memo` + stable callbacks from the parent keep re-renders
 * limited to cards whose props actually change (e.g. the one currently
 * syncing). The whole card is keyboard accessible: the name is a focusable
 * link and the actions are a focusable menu.
 */
export const RepositoryCard = memo(function RepositoryCard({
  repository,
  syncing,
  searchQuery,
  onSync,
  onDelete,
}: RepositoryCardProps) {
  const name = repositoryName(repository.full_name);
  const owner = repositoryOwner(repository.full_name);
  const visibleTopics = repository.topics.slice(0, MAX_VISIBLE_TOPICS);
  const hiddenTopics = repository.topics.length - visibleTopics.length;

  return (
    <article
      data-slot="repository-card"
      className="group/card flex flex-col gap-3.5 rounded-xl bg-card p-4 text-sm text-card-foreground ring-1 ring-foreground/10 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/5 hover:ring-primary/40 focus-within:ring-primary/40"
    >
      {/* Header: name + owner + actions */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/15 transition-colors group-hover/card:bg-primary/15">
            <BookOpen className="size-4" aria-hidden />
          </div>
          <div className="min-w-0">
            <Link
              href={`/app/repositories/${repository.id}`}
              className="block truncate text-sm font-semibold text-foreground transition-colors hover:text-primary"
            >
              <SearchHighlight text={name} query={searchQuery} />
            </Link>
            <p className="truncate text-xs text-muted-foreground">
              <SearchHighlight text={owner} query={searchQuery} />
            </p>
          </div>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${repository.full_name}`}>
                <MoreHorizontal className="size-4" />
              </Button>
            }
          />
          <DropdownMenuContent align="end" className="w-44">
            <DropdownMenuGroup>
              <DropdownMenuLabel>{repository.full_name}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                render={<Link href={`/app/repositories/${repository.id}`} />}
              >
                <Eye className="size-4" />
                View details
              </DropdownMenuItem>
              <DropdownMenuItem disabled={syncing} onClick={() => onSync(repository)}>
                <RefreshCw className={syncing ? "animate-spin" : ""} />
                {syncing ? "Syncing…" : "Refresh metadata"}
              </DropdownMenuItem>
              {repository.html_url ? (
                <DropdownMenuItem
                  render={
                    <a href={repository.html_url} target="_blank" rel="noreferrer noopener" />
                  }
                >
                  <ExternalLink className="size-4" />
                  Open on GitHub
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => onDelete(repository)}>
                <Trash2 className="size-4" />
                Remove
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Description */}
      <p className="line-clamp-2 min-h-8 text-xs leading-5 text-muted-foreground">
        {repository.description ? (
          <SearchHighlight text={repository.description} query={searchQuery} />
        ) : (
          <span className="italic">No description provided.</span>
        )}
      </p>

      {/* Badges: status, visibility, language */}
      <div className="flex flex-wrap items-center gap-1.5">
        <AnalysisStatusBadge status={repository.analysis_status} />
        {repository.is_private ? (
          <Badge variant="secondary" className="gap-1">
            <Lock className="size-3" aria-hidden />
            Private
          </Badge>
        ) : (
          <Badge variant="outline">Public</Badge>
        )}
        {repository.language ? (
          <Badge variant="outline" className="gap-1.5">
            <span
              aria-hidden
              className={`size-1.5 rounded-full ${languageDotClass(repository.language)}`}
            />
            {repository.language}
          </Badge>
        ) : null}
        {repository.archived ? <Badge variant="outline">Archived</Badge> : null}
        {!repository.is_active ? <Badge variant="destructive">Unavailable</Badge> : null}
      </div>

      {/* Topic chips */}
      {visibleTopics.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {visibleTopics.map((topic) => (
            <span
              key={topic}
              className="rounded-full bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground"
            >
              {topic}
            </span>
          ))}
          {hiddenTopics > 0 ? (
            <span className="rounded-full bg-secondary/60 px-2 py-0.5 text-[11px] text-muted-foreground">
              +{hiddenTopics} more
            </span>
          ) : null}
        </div>
      ) : null}

      {/* Stats */}
      <dl className="grid grid-cols-2 gap-2 rounded-lg bg-muted/50 p-2.5 sm:grid-cols-4">
        <Stat icon={Star} label="Stars" value={compactNumber(repository.stars)} />
        <Stat icon={GitFork} label="Forks" value={compactNumber(repository.forks)} />
        <Stat icon={GitBranch} label="Issues" value={compactNumber(repository.open_issues)} />
        <Stat
          icon={BookOpen}
          label="Branch"
          value={repository.default_branch || "–"}
          title={repository.default_branch || undefined}
        />
      </dl>

      {/* Footer: updated / imported / synced */}
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <span
            aria-hidden
            className={`size-1.5 rounded-full ${languageDotClass(repository.language)}`}
          />
          Updated {relativeTime(repository.pushed_at)}
        </span>
        <span className="inline-flex items-center gap-1.5">
          {syncing ? (
            <Loader2 className="size-3 animate-spin" aria-hidden />
          ) : (
            <RefreshCw className="size-3" aria-hidden />
          )}
          {syncing
            ? "Syncing…"
            : `Imported ${relativeTime(repository.created_at)}`}
          {!syncing ? (
            <span className="text-muted-foreground/70">
              · synced {relativeTime(repository.last_synced_at)}
            </span>
          ) : null}
        </span>
      </div>
    </article>
  );
});

function Stat({
  icon: Icon,
  label,
  value,
  title,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-0.5 text-center">
      <dt className="flex items-center gap-1 text-[10px] tracking-wide text-muted-foreground uppercase">
        <Icon className="size-3" aria-hidden />
        {label}
      </dt>
      <dd className="text-sm font-medium text-foreground" title={title}>
        {value}
      </dd>
    </div>
  );
}
