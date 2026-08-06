/**
 * Formatting helpers — dates and numbers for repository cards/detail pages.
 * Pure functions, no dependencies beyond Intl.
 */

/** "3d ago", "2h ago", "just now" — GitHub-style relative time. */
export function relativeTime(value: string | null | undefined): string {
  if (!value) return "Never";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "Never";

  const seconds = Math.round((then - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["week", 60 * 60 * 24 * 7],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
  ];
  for (const [unit, divisor] of units) {
    if (abs >= divisor) {
      return formatter.format(Math.round(seconds / divisor), unit);
    }
  }
  return "just now";
}

/** 42 -> "42", 12500 -> "12.5k", 2_400_000 -> "2.4M". */
export function compactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

/** GitHub `size` is KiB → human-readable. */
export function formatSizeKb(sizeKb: number | null | undefined): string {
  if (sizeKb === null || sizeKb === undefined) return "–";
  if (sizeKb < 1024) return `${Math.round(sizeKb)} KB`;
  return `${(sizeKb / 1024).toFixed(1)} MB`;
}

/** "2024-01-01T10:00:00Z" -> "Jan 1, 2024". */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Never";
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

/** `owner/name` -> owner for display. */
export function languageDotClass(language: string | null): string {
  // A small curated palette of GitHub language colors; unknown languages
  // fall back to neutral. Kept intentionally short — not an exhaustive map.
  const palette: Record<string, string> = {
    TypeScript: "bg-blue-500",
    JavaScript: "bg-yellow-400",
    Python: "bg-emerald-400",
    Go: "bg-cyan-400",
    Rust: "bg-orange-600",
    Java: "bg-red-500",
    "C++": "bg-pink-500",
    C: "bg-zinc-400",
    "C#": "bg-purple-500",
    Ruby: "bg-rose-600",
    PHP: "bg-indigo-400",
    Swift: "bg-orange-500",
    Kotlin: "bg-violet-500",
    Shell: "bg-lime-400",
    HTML: "bg-orange-400",
    CSS: "bg-sky-400",
    Dockerfile: "bg-blue-400",
    Vue: "bg-green-500",
    Svelte: "bg-orange-500",
    Jupyter: "bg-orange-600",
  };
  return language ? (palette[language] ?? "bg-zinc-500") : "bg-zinc-500";
}
