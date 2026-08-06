import { ShieldCheck, Lock, Globe } from "lucide-react";

const TOOLS = [
  {
    name: "Trivy",
    role: "Container & dependency vulnerabilities",
    detail: "Comprehensive CVE scanning for images, filesystems and repos.",
  },
  {
    name: "Syft",
    role: "SBOM generation",
    detail: "Builds a full software bill of materials from any artifact.",
  },
  {
    name: "Grype",
    role: "Vulnerability matching",
    detail: "Fast, accurate matching against multiple CVE databases.",
  },
  {
    name: "Semgrep",
    role: "Code & IaC analysis",
    detail: "Static analysis for risky code, configs and infrastructure.",
  },
  {
    name: "Gitleaks",
    role: "Secret detection",
    detail: "Catches leaked credentials before they hit your pipeline.",
  },
];

const PRINCIPLES = [
  { icon: Lock, text: "Scans run in your own environment — findings, not raw code, leave the perimeter." },
  { icon: ShieldCheck, text: "Every scanner is pinned and verified. Nothing ships untrusted." },
  { icon: Globe, text: "Open-source tooling, so the supply chain that guards you is inspectable too." },
];

export function SecurityStack() {
  return (
    <section id="stack" className="scroll-mt-20 py-20 sm:py-28">
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-primary">Security stack</p>
          <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            Powered by the scanners the industry trusts
          </h2>
          <p className="mt-4 text-pretty text-base leading-7 text-muted-foreground">
            We orchestrate battle-tested open-source tools behind a single API,
            so you get enterprise-grade coverage without the enterprise lock-in.
          </p>
        </div>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.map((tool) => (
            <div
              key={tool.name}
              className="rounded-xl border border-border bg-card p-6 transition-colors hover:border-primary/40"
            >
              <div className="flex items-center gap-3">
                <div className="flex size-9 items-center justify-center rounded-lg bg-muted font-mono text-xs font-semibold">
                  {tool.name.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3 className="text-sm font-medium">{tool.name}</h3>
                  <p className="text-xs text-muted-foreground">{tool.role}</p>
                </div>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                {tool.detail}
              </p>
            </div>
          ))}

          <div className="flex flex-col justify-center gap-4 rounded-xl border border-dashed border-border bg-muted/20 p-6">
            {PRINCIPLES.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-start gap-3">
                <Icon className="mt-0.5 size-4 shrink-0 text-primary" />
                <p className="text-sm leading-6 text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
