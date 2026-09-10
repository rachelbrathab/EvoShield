"use client";

import { Activity, GitBranch, Radar, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/lib/auth";
import {
  ANALYSIS_STATUSES,
  ANALYSIS_STATUS_META,
} from "@/lib/repository";

import { AnalysisStatusBadge } from "@/components/repositories/analysis-status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const LIVE_MODULES = [
  {
    title: "Manage repositories",
    description:
      "Connect GitHub, import repositories and keep their metadata in sync.",
    icon: GitBranch,
    href: "/app/repositories",
  },
  {
    title: "Run security analysis",
    description:
      "Multi-scanner pipeline: Trivy, Gitleaks, Semgrep and Grype/Syft in one pass.",
    icon: Activity,
    href: "/app/analysis",
  },
  {
    title: "Intelligence & remediation",
    description:
      "Risk score, prioritized findings and remediation guidance on every run.",
    icon: Radar,
    href: "/app/analysis",
  },
];

export default function AppDashboardPage() {
  const { user } = useAuth();

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">
          Welcome back{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}
        </h2>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Import a repository, run the multi-scanner pipeline and work the
          findings — from raw scanner output to remediation in one place.
        </p>
      </section>

      {/* Pipeline status strip */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="size-4 text-primary" />
            Account status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs text-muted-foreground">Signed in as</dt>
              <dd className="mt-1 truncate text-sm font-medium text-foreground">
                {user?.email}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Auth provider</dt>
              <dd className="mt-1 text-sm font-medium text-foreground capitalize">
                {user?.auth_provider}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Pipeline stage</dt>
              <dd className="mt-1 text-sm font-medium text-foreground">
                Multi-scanner analysis · Trivy, Gitleaks, Semgrep, Grype
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Analysis status vocabulary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="size-4 text-primary" />
            Analysis status
          </CardTitle>
          <CardDescription className="text-xs leading-5">
            Every repository carries one of these lifecycle states. Repository
            cards and detail pages render them live as analyses queue, run and
            complete.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {ANALYSIS_STATUSES.map((status) => (
              <li key={status} className="flex items-center justify-between gap-3">
                <AnalysisStatusBadge status={status} />
                <span className="text-xs text-muted-foreground">
                  {ANALYSIS_STATUS_META[status].description}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Live modules */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-medium text-foreground">Available now</h3>
          <Link
            href="/app/repositories"
            className="inline-flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80"
          >
            Open repositories <span aria-hidden>→</span>
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {LIVE_MODULES.map((item) => (
            <Link key={item.title} href={item.href} className="group">
              <Card className="h-full border-primary/30 transition-colors group-hover:border-primary/60">
                <CardHeader>
                  <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <item.icon className="size-5" />
                  </div>
                  <CardTitle className="text-sm">{item.title}</CardTitle>
                  <CardDescription className="text-xs leading-5">
                    {item.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <span className="inline-flex items-center gap-1 text-xs text-primary transition-opacity group-hover:opacity-100">
                    Open <span aria-hidden>→</span>
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
