import { cn } from "@/lib/utils";

/** Historical bars (actual) followed by forecast bars (predicted). */
const HISTORY = [42, 46, 44, 51, 49, 55, 58, 61, 59, 66, 70, 72];
const FORECAST = [76, 79, 84];

export function RiskChart() {
  const bars = [
    ...HISTORY.map((value) => ({ value, predicted: false })),
    ...FORECAST.map((value) => ({ value, predicted: true })),
  ];
  const max = 100;

  return (
    <div className="mt-4 flex h-28 items-end gap-1.5">
      {bars.map(({ value, predicted }, index) => (
        <div
          key={index}
          className="group relative flex flex-1 flex-col items-center justify-end gap-1.5"
        >
          <span className="pointer-events-none absolute -top-6 rounded bg-muted px-1 py-0.5 font-mono text-[10px] text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
            {value}
          </span>
          <div
            className={cn(
              "w-full rounded-sm transition-all duration-300 group-hover:opacity-80",
              predicted
                ? "bg-gradient-to-t from-primary/70 to-primary"
                : "bg-gradient-to-t from-zinc-600 to-zinc-400",
            )}
            style={{ height: `${(value / max) * 100}%` }}
          />
        </div>
      ))}
    </div>
  );
}
