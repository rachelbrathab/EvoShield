import { buttonVariants } from "@/components/ui/button";
import { GitHubIcon } from "@/components/site/github-icon";
import { cn } from "@/lib/utils";

const FEATURE_LINKS = [
  { label: "Product", href: "#features" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Security stack", href: "#stack" },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-border/60">
      <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <GitHubIcon className="size-5 text-primary" />
              <span className="text-sm font-semibold">EvoShield</span>
            </div>
            <p className="max-w-xs text-sm leading-6 text-muted-foreground">
              Predictive software supply chain risk assessment using temporal
              repository intelligence.
            </p>
            <p className="text-xs text-muted-foreground/70">
              © {new Date().getFullYear()} EvoShield · Final year engineering project
            </p>
          </div>

          <div>
            <h3 className="text-sm font-medium text-foreground">Product</h3>
            <ul className="mt-3 space-y-2">
              {FEATURE_LINKS.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-medium text-foreground">Security stack</h3>
            <ul className="mt-3 space-y-2">
              {["Trivy", "Syft", "Grype", "Semgrep", "Gitleaks"].map((tool) => (
                <li key={tool} className="text-sm text-muted-foreground">
                  {tool}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-medium text-foreground">Status</h3>
            <div className="mt-3">
              <a
                href="#"
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                  "w-full justify-center",
                )}
              >
                API status
              </a>
            </div>
            <p className="mt-3 text-xs leading-5 text-muted-foreground/70">
              Sprint 1 of 14 — project setup. Authentication ships in Sprint 2.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
