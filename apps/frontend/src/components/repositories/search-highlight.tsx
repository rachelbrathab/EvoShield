"use client";

import { highlightSegments } from "@/lib/search";

/**
 * Renders `text` with case-insensitive `query` matches wrapped in `<mark>`.
 * Used by repository cards so the active search term stands out. When the
 * query is empty the text renders unchanged (no wrapper elements).
 */
export function SearchHighlight({
  text,
  query,
  className,
}: {
  text: string;
  query?: string;
  className?: string;
}) {
  const segments = highlightSegments(text, query ?? "");
  if (segments.length === 1 && !segments[0]?.highlighted) {
    return <>{text}</>;
  }
  return (
    <>
      {segments.map((segment, index) =>
        segment.highlighted ? (
          <mark
            key={index}
            className="rounded-[3px] bg-primary/25 px-0.5 text-foreground"
          >
            {segment.text}
          </mark>
        ) : (
          <span key={index} className={className}>
            {segment.text}
          </span>
        ),
      )}
    </>
  );
}
