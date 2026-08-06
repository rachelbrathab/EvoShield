import {
  GitBranch,
  ListChecks,
  ScanLine,
  Brain,
  ArrowRight,
} from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STEPS = [
  {
    icon: GitBranch,
    step: "01",
    title: "Connect",
    description:
      "Authenticate with GitHub and choose the repositories you want to protect. EvoShield indexes manifests, releases and commit history.",
  },
  {
    icon: ScanLine,
    step: "02",
    title: "Scan",
    description:
      "Syft builds an SBOM, Trivy and Grype find vulnerabilities, Gitleaks hunts secrets and Semgrep reviews code patterns — in parallel.",
  },
  {
    icon: Brain,
    step: "03",
    title: "Predict",
    description:
      "Our scikit-learn engine models risk over time and forecasts your score 90 days ahead, complete with confidence intervals.",
  },
  {
    icon: ListChecks,
    step: "04",
    title: "Remediate",
    description:
      "Prioritised, actionable recommendations tell you exactly what to fix first — and how it will move your predicted score.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-y border-border/60 bg-muted/20 py-20 sm:py-28">
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
        <div className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-end">
          <div className="max-w-2xl">
            <p className="text-sm font-medium text-primary">How it works</p>
            <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
              From repository to remediation in four steps
            </h2>
          </div>
          <a
            href="#"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            Read the docs <ArrowRight className="size-4" />
          </a>
        </div>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ icon: Icon, step, title, description }, index) => (
            <div
              key={step}
              className="relative rounded-xl border border-border bg-card p-6"
            >
              <div className="flex items-center justify-between">
                <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </div>
                <span className="font-mono text-xs text-muted-foreground">
                  {step}
                </span>
              </div>
              <h3 className="mt-4 text-base font-medium">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {description}
              </p>
              {index < STEPS.length - 1 ? (
                <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden size-4 -translate-y-1/2 text-muted-foreground/40 lg:block" />
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
