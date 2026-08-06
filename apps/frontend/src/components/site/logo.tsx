import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <svg
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
        className="size-6 shrink-0"
      >
        <path
          d="M12 2.4 4.6 5.4v5.3c0 4.6 3.2 8.8 7.4 10 4.2-1.2 7.4-5.4 7.4-10V5.4L12 2.4Z"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
          className="text-primary/40"
        />
        <path
          d="M12 5.9v12.2M8.9 9.2h6.2M8.9 12.4h4.4"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          className="text-primary"
        />
        <path
          d="M12 6.9l3.4 1.9-2.4 1.5L12 6.9Z"
          fill="currentColor"
          className="text-primary"
        />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-foreground">
        Evo<span className="text-primary">Shield</span>
      </span>
    </span>
  );
}
