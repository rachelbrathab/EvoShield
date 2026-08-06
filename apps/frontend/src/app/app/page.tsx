"use client";

import {
  ArrowRight,
  GitBranch,
  LineChart,
  Radar,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/lib/auth";
import {
  ANALYSIS_STATUSES,
  ANALYSIS_STATUS_META,
} from "@/lib/repository";

import { AnalysisStatusBadge } from "@/components/repositories/analysis-status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const COMING_SOON = [
  {
    title: "Connect repositories",
    description: "Link a GitHub repository to start scanning its supply chain.",
    icon: GitBranch,
    href: "/app/repositories",
  },
  {
    title: "Run security analysis",
    description: "SBOM, vulnerabilities, secrets and code analysis in one pass.",
    icon: Radar,
    href: "/app/analysis",
  },
  {
    title: "Forecast risk",
    description: "Temporal repository intelligence predicts where risk is heading.",
    icon: LineChart,
    href: "/app/predictions",
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
          Your workspace is ready. The DevSecOps pipeline ships over the next
          sprints — here is what is coming.
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
                Sprint 3 · Repository integration
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Analysis status vocabulary — placeholder badges Sprint 3 cards reuse */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Radar className="size-4 text-primary" />
            Analysis status
          </CardTitle>
          <CardDescription className="text-xs leading-5">
            Every repository carries one of these lifecycle states. Repository
            cards and detail pages will render them once repository
            integration lands — no analysis functionality yet.
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

      {/* Coming-soon modules */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-medium text-foreground">Coming soon</h3>
          <Link
            href="/app/repositories"
            className="inline-flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80"
          >
            Repositories <ArrowRight className="size-3" />
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {COMING_SOON.map((item) => (
            <Link key={item.title} href={item.href} className="group">
              <Card className="h-full transition-colors group-hover:border-primary/40">
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
                  <span className="inline-flex items-center gap-1 text-xs text-primary opacity-0 transition-opacity group-hover:opacity-100">
                    Explore <ArrowRight className="size-3" />
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
