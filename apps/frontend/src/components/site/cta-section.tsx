import { ArrowRight, ShieldCheck } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function CtaSection() {
  return (
    <section className="pb-24 sm:pb-32">
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
        <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-primary/20 via-card to-card p-10 sm:p-16">
          <div
            className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-primary/20 blur-3xl"
            aria-hidden="true"
          />
          <div className="relative mx-auto max-w-2xl text-center">
            <div className="mx-auto mb-6 flex size-12 items-center justify-center rounded-xl bg-primary/15 text-primary">
              <ShieldCheck className="size-6" />
            </div>
            <h2 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
              Your software supply chain, 90 days ahead of attackers
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-pretty text-base leading-7 text-muted-foreground">
              Connect a repository and get your first SBOM, vulnerability report
              and risk forecast in minutes. Free during development — no credit
              card required.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <a
                href="/register"
                className={cn(buttonVariants({ size: "lg" }), "h-11 px-6 text-sm")}
              >
                Get started free <ArrowRight className="size-4" />
              </a>
              <a
                href="/login"
                className={cn(
                  buttonVariants({ variant: "outline", size: "lg" }),
                  "h-11 px-6 text-sm",
                )}
              >
                Sign in
              </a>
            </div>
            <p className="mt-5 text-xs text-muted-foreground">
              Built as a final year engineering project · EvoShield
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
