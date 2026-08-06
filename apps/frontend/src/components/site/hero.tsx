import {
  Activity,
  AlertTriangle,
  ArrowRight,
  GitBranch,
  LineChart,
  ScanLine,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { GitHubIcon } from "@/components/site/github-icon";
import { RiskChart } from "@/components/site/risk-chart";
import { cn } from "@/lib/utils";

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* Backdrop */}
      <div className="pointer-events-none absolute inset-0 bg-grid mask-fade-b" aria-hidden="true" />
      <div
        className="pointer-events-none absolute -top-40 left-1/2 h-[480px] w-[820px] -translate-x-1/2 rounded-full bg-primary/15 blur-[120px]"
        aria-hidden="true"
      />

      <div className="relative mx-auto w-full max-w-6xl px-5 pb-20 pt-20 sm:px-8 sm:pt-28">
        <div className="mx-auto max-w-3xl text-center">
          <Badge variant="outline" className="mb-6 gap-1.5 rounded-full px-3 py-1">
            <Sparkles className="size-3 text-primary" />
            Predictive supply chain security
          </Badge>

          <h1 className="text-balance text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
            See your supply chain risk{" "}
            <span className="text-gradient">before it ships</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-7 text-muted-foreground sm:text-lg">
            EvoShield connects your GitHub repositories, scans dependencies,
            secrets and IaC with industry-grade tooling, then forecasts where
            risk is heading — so you can remediate before attackers exploit it.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="#"
              className={cn(buttonVariants({ size: "lg" }), "h-11 px-6 text-sm")}
            >
              Start scanning <ArrowRight className="size-4" />
            </a>
            <a
              href="#how-it-works"
              className={cn(
                buttonVariants({ variant: "outline", size: "lg" }),
                "h-11 px-6 text-sm",
              )}
            >
              See how it works
            </a>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="size-3.5 text-emerald-400" />
              Open-source scanners
            </span>
            <span className="inline-flex items-center gap-1.5">
              <LineChart className="size-3.5 text-primary" />
              ML-driven forecasts
            </span>
            <span className="inline-flex items-center gap-1.5">
              <GitHubIcon className="size-3.5" />
              Native GitHub integration
            </span>
          </div>
        </div>

        {/* Product mock */}
        <div className="relative mx-auto mt-16 max-w-5xl">
          <div className="absolute -inset-3 rounded-2xl bg-gradient-to-b from-primary/20 via-transparent to-transparent blur-2xl" aria-hidden="true" />
          <div className="relative overflow-hidden rounded-xl border border-border bg-card shadow-2xl shadow-black/40">
            {/* Window chrome */}
            <div className="flex items-center gap-2 border-b border-border/60 bg-muted/30 px-4 py-2.5">
              <span className="size-2.5 rounded-full bg-rose-500/80" />
              <span className="size-2.5 rounded-full bg-amber-500/80" />
              <span className="size-2.5 rounded-full bg-emerald-500/80" />
              <span className="ml-3 font-mono text-xs text-muted-foreground">
                app.evoshield.dev/repositories/acme-core
              </span>
              <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400">
                <span className="size-1.5 animate-pulse rounded-full bg-emerald-400" />
                Scan complete
              </span>
            </div>

            <div className="grid gap-px bg-border/50 md:grid-cols-[240px_1fr]">
              {/* Sidebar */}
              <div className="hidden gap-1 p-4 md:flex md:flex-col">
                {[
                  { icon: Activity, label: "Overview", active: true },
                  { icon: GitBranch, label: "Repositories", count: "12" },
                  { icon: ScanLine, label: "Scans", count: "4" },
                  { icon: LineChart, label: "Predictions" },
                ].map(({ icon: Icon, label, count, active }) => (
                  <div
                    key={label}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm",
                      active
                        ? "bg-primary/15 font-medium text-primary"
                        : "text-muted-foreground",
                    )}
                  >
                    <Icon className="size-4" />
                    {label}
                    {count ? (
                      <span className="ml-auto rounded-full bg-muted px-1.5 text-[11px] text-muted-foreground">
                        {count}
                      </span>
                    ) : null}
                  </div>
                ))}
              </div>

              {/* Main panel */}
              <div className="space-y-5 bg-card p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">acme-core</p>
                    <p className="text-xs text-muted-foreground">
                      Risk forecast · next 90 days
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-md border border-border px-2 py-1 font-mono text-xs text-muted-foreground">
                      24 findings
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-md bg-destructive/10 px-2 py-1 font-mono text-xs text-destructive">
                      <AlertTriangle className="size-3" /> 3 high
                    </span>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="rounded-lg border border-border bg-muted/20 p-4">
                    <p className="text-xs text-muted-foreground">Current risk</p>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="text-3xl font-semibold tracking-tight">72</span>
                      <span className="text-xs text-muted-foreground">/ 100</span>
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/20 p-4">
                    <p className="text-xs text-muted-foreground">Predicted (90d)</p>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="text-3xl font-semibold tracking-tight text-primary">84</span>
                      <span className="inline-flex items-center gap-1 text-xs text-rose-400">
                        <TrendingUp className="size-3" /> +12
                      </span>
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/20 p-4">
                    <p className="text-xs text-muted-foreground">Confidence</p>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="text-3xl font-semibold tracking-tight">87%</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-border bg-muted/20 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium">Risk trajectory</p>
                    <p className="text-[11px] text-muted-foreground">actual → predicted</p>
                  </div>
                  <RiskChart />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
