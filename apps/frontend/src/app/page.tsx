import { CtaSection } from "@/components/site/cta-section";
import { Features } from "@/components/site/features";
import { Hero } from "@/components/site/hero";
import { HowItWorks } from "@/components/site/how-it-works";
import { SecurityStack } from "@/components/site/security-stack";
import { SiteFooter } from "@/components/site/site-footer";
import { SiteHeader } from "@/components/site/site-header";

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <Features />
        <HowItWorks />
        <SecurityStack />
        <CtaSection />
      </main>
      <SiteFooter />
    </div>
  );
}
