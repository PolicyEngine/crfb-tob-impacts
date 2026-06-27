"use client";

import { ArrowRight, BookOpenText, Database, FlaskConical } from "lucide-react";

import { TobExplainerSection } from "@/components/tob-explainer-section";

type ReformLink = {
  id: string;
  shortName: string;
  description: string;
};

function FamilyCard({
  title,
  blurb,
  reforms,
  onSelect,
}: {
  title: string;
  blurb: string;
  reforms: ReformLink[];
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex flex-col overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
      <div className="border-b border-[var(--pe-color-border-light)] px-5 py-4">
        <h4 className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--pe-color-primary-700)]">
          {title}
        </h4>
        <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
          {blurb}
        </p>
      </div>
      <ul className="divide-y divide-[var(--pe-color-border-light)]">
        {reforms.map((reform) => (
          <li key={reform.id}>
            <button
              type="button"
              onClick={() => onSelect(reform.id)}
              className="group flex w-full items-center justify-between gap-3 px-5 py-3 text-left transition hover:bg-[var(--pe-color-bg-secondary)]"
            >
              <span className="min-w-0">
                <span className="block text-sm font-medium text-[var(--pe-color-text-primary)]">
                  {reform.shortName}
                </span>
                <span className="mt-0.5 block truncate text-xs text-[var(--pe-color-text-tertiary)]">
                  {reform.description}
                </span>
              </span>
              <ArrowRight className="h-4 w-4 shrink-0 text-[var(--pe-color-text-tertiary)] transition group-hover:translate-x-0.5 group-hover:text-[var(--pe-color-primary-700)]" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AboutLink({
  icon,
  title,
  description,
  onClick,
  href,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick?: () => void;
  href?: string;
}) {
  const inner = (
    <>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--pe-color-bg-secondary)] text-[var(--pe-color-primary-700)]">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-[var(--pe-color-text-title)]">
          {title}
        </span>
        <span className="mt-0.5 block text-xs leading-5 text-[var(--pe-color-text-tertiary)]">
          {description}
        </span>
      </span>
    </>
  );
  const className =
    "flex items-center gap-3 rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-4 py-3 text-left transition hover:border-[var(--pe-color-primary-300)] hover:bg-[var(--pe-color-bg-secondary)]";
  if (href) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={className}>
        {inner}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} className={className}>
      {inner}
    </button>
  );
}

export function HomeOverview({
  benefitReforms,
  structuralReforms,
  onSelectReform,
  onOpenMethodology,
  onOpenBaseline,
  paperHref,
}: {
  benefitReforms: ReformLink[];
  structuralReforms: ReformLink[];
  onSelectReform: (id: string) => void;
  onOpenMethodology: () => void;
  onOpenBaseline: () => void;
  paperHref: string;
}) {
  return (
    <div className="flex flex-col gap-10">
      {/* What this is + how to use it */}
      <section className="max-w-3xl space-y-4 text-lg leading-8 text-[var(--pe-color-text-secondary)]">
        <p>
          This dashboard shows how proposed reforms to the federal income
          taxation of Social Security benefits would affect federal revenue and
          the Social Security (OASDI) and Medicare (HI) trust funds, year by
          year through 2100.
        </p>
        <p className="text-base leading-7">
          Choose a reform from the sidebar to see its revenue impact, trust-fund
          split, and effect across the income distribution. Each reform can be
          scored against scheduled benefits or against a Social Security
          solvency baseline. Start with the explainer below for how benefit taxation
          works today.
        </p>
      </section>

      {/* How taxation of benefits works today */}
      <TobExplainerSection />

      {/* Explore the reforms — points to the sidebar, works on mobile */}
      <section>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h3 className="text-xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
            Explore the reforms
          </h3>
          <span className="hidden text-sm text-[var(--pe-color-text-tertiary)] xl:inline">
            Or choose one from the sidebar on the left
          </span>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <FamilyCard
            title="Benefit tax rules"
            blurb="Change how much of Social Security benefits is subject to income tax — from full repeal to taxing 100% of benefits."
            reforms={benefitReforms}
            onSelect={onSelectReform}
          />
          <FamilyCard
            title="Structural swaps"
            blurb="Replace benefit taxation with a different mechanism, such as taxing contributions up front instead of benefits in retirement."
            reforms={structuralReforms}
            onSelect={onSelectReform}
          />
        </div>
      </section>

      {/* Where the numbers come from */}
      <section>
        <h3 className="text-xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
          How the analysis works
        </h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <AboutLink
            icon={<FlaskConical className="h-4 w-4" />}
            title="Methodology"
            description="How reforms are modeled and projected to 2100"
            onClick={onOpenMethodology}
          />
          <AboutLink
            icon={<Database className="h-4 w-4" />}
            title="Baseline model"
            description="Trustees assumptions and calibration targets"
            onClick={onOpenBaseline}
          />
          <AboutLink
            icon={<BookOpenText className="h-4 w-4" />}
            title="Citable paper"
            description="Full narrative, methodology, and sources"
            href={paperHref}
          />
        </div>
      </section>
    </div>
  );
}
