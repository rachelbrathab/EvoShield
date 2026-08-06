"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/site/logo";
import { cn } from "@/lib/utils";

/**
 * Shared shell for /login and /register: a centered card with the EvoShield
 * brand, an optional GitHub OAuth entry point, and the form itself.
 */
export function AuthCard({
  title,
  subtitle,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center bg-grid px-4 py-12">
      {/* Ambient glow behind the card */}
      <div
        className="pointer-events-none absolute left-1/2 top-1/3 size-[28rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/10 blur-3xl"
        aria-hidden="true"
      />

      <div className="relative w-full max-w-sm">
        <Link href="/" className="mb-8 flex justify-center" aria-label="EvoShield home">
          <Logo />
        </Link>

        <div className="rounded-2xl border border-border bg-card/70 p-7 shadow-2xl backdrop-blur-xl">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>

          <div className="mt-6">{children}</div>
        </div>

        {footer ? (
          <div className={cn("mt-6 text-center")}>{footer}</div>
        ) : null}
      </div>

      <p className="relative mt-10 text-xs text-muted-foreground/70">
        EvoShield · Predictive software supply chain security
      </p>
    </div>
  );
}
