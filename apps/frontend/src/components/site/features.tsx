import {
  Boxes,
  Brain,
  Bug,
  Fingerprint,
  LineChart,
  GitPullRequest,
} from "lucide-react";

const FEATURES = [
  {
    icon: GitPullRequest,
    title: "Connect repositories",
    description:
      "One-click GitHub integration. EvoShield watches your repositories, dependency manifests and release history automatically.",
  },
  {
    icon: Boxes,
    title: "SBOM generation",
    description:
      "Syft builds a software bill of materials for every repository, so you always know exactly what is shipping and where it came from.",
  },
  {
    icon: Bug,
    title: "Vulnerability scanning",
    description:
      "Trivy and Grype cross-reference your dependencies and containers against the latest CVE feeds — no false-positive noise.",
  },
  {
    icon: Fingerprint,
    title: "Secrets & code risk",
    description:
      "Gitleaks catches leaked credentials and Semgrep flags risky code patterns before they reach production.",
  },
  {
    icon: LineChart,
    title: "Temporal intelligence",
    description:
      "Risk is tracked over time. See how exposure drifts across releases, dependencies and team changes — not just a point-in-time snapshot.",
  },
  {
    icon: Brain,
    title: "Predictive forecasting",
    description:
      "A scikit-learn model forecasts where your risk score is heading over the next 90 days, with confidence intervals you can act on.",
  },
];

export function Features() {
  return (
    <section id="features" className="relative scroll-mt-20 py-20 sm:py-28">
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-primary">Capabilities</p>
          <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            Everything you need to defend the software supply chain
          </h2>
          <p className="mt-4 text-pretty text-base leading-7 text-muted-foreground">
            Six integrated layers — from repository connection to predictive
            forecasting — each built to production standards and stitched
            together by a single risk model.
          </p>
        </div>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="group relative overflow-hidden rounded-xl border border-border bg-card p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5"
            >
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary/20">
                <Icon className="size-5" />
              </div>
              <h3 className="mt-4 text-base font-medium">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
