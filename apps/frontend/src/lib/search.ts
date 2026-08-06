/**
 * Search utilities for the repository list.
 *
 * `highlightSegments` is a pure function so it can be unit-tested and reused
 * by the `<SearchHighlight>` component without React coupling.
 */

export type HighlightSegment = {
  text: string;
  highlighted: boolean;
};

/**
 * Split `text` into segments, marking the parts that match `query`
 * (case-insensitive). Empty/whitespace queries return a single plain segment.
 *
 * ```ts
 * highlightSegments("Hello World", "ell") // [{text:"H",…},{text:"ell",highlighted:true},{text:"o World",…}]
 * ```
 */
export function highlightSegments(text: string, query: string): HighlightSegment[] {
  const trimmed = query.trim();
  if (!trimmed || !text) return [{ text, highlighted: false }];

  // `toLowerCase` (not `toLocaleLowerCase`) keeps matching deterministic
  // across locales — e.g. a Turkish runtime would otherwise fail to match
  // "I" against "i".
  const needle = trimmed.toLowerCase();
  const haystack = text.toLowerCase();
  const segments: HighlightSegment[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    const matchAt = haystack.indexOf(needle, cursor);
    if (matchAt === -1) {
      segments.push({ text: text.slice(cursor), highlighted: false });
      break;
    }
    if (matchAt > cursor) {
      segments.push({ text: text.slice(cursor, matchAt), highlighted: false });
    }
    segments.push({
      text: text.slice(matchAt, matchAt + needle.length),
      highlighted: true,
    });
    cursor = matchAt + needle.length;
  }
  return segments;
}
