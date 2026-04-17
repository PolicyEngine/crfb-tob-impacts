"use client";

import { useState } from "react";

import { MethodologyDiagram } from "@/components/methodology-diagram";

function AccordionItem({
  title,
  summary,
  defaultOpen = false,
  children,
}: {
  title: string;
  summary: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
      <button
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left"
        aria-expanded={isOpen}
      >
        <div>
          <h3 className="text-base font-semibold text-[var(--pe-color-text-title)]">
            {title}
          </h3>
          <p className="mt-1 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
            {summary}
          </p>
        </div>
        <span className="mt-1 text-lg leading-none text-[var(--pe-color-text-tertiary)]">
          {isOpen ? "−" : "+"}
        </span>
      </button>
      {isOpen ? (
        <div className="border-t border-[var(--pe-color-border-light)] px-5 py-4 text-sm leading-7 text-[var(--pe-color-text-secondary)]">
          {children}
        </div>
      ) : null}
    </div>
  );
}

function BulletList({ children }: { children: React.ReactNode }) {
  return <ul className="ml-5 list-disc space-y-1">{children}</ul>;
}

export function MethodologySection() {
  return (
    <section className="space-y-4 border-t border-[var(--pe-color-border-light)] pt-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
          Methods and sources
        </h2>
        <p className="mt-2 text-sm text-[var(--pe-color-text-secondary)]">
          Summary methodology. See the{" "}
          <a href="/paper/" target="_blank" rel="noreferrer" className="text-[var(--pe-color-primary-700)] hover:underline">
            citable paper
          </a>{" "}
          for the full methodology and bibliography.
        </p>
      </div>

      <MethodologyDiagram />

      <div className="space-y-4">
        <AccordionItem
          title="Two-Stage Projection Methodology"
          summary="75-year projections use economic uprating followed by positive-entropy calibration to match Trustees Report targets."
          defaultOpen
        >
          <p>
            <strong>Stage 1: Economic Uprating</strong> — PolicyEngine projects each household&apos;s
            economic circumstances forward using official macroeconomic assumptions from the
            2025 Social Security Trustees Report.
          </p>
          <BulletList>
            <li>Employment income follows wage growth (AWI) projections.</li>
            <li>Social Security benefits follow COLA projections.</li>
            <li>Capital gains follow asset appreciation projections.</li>
            <li>Tax parameters are uprated according to statutory indexing rules.</li>
          </BulletList>
          <p className="mt-4">
            <strong>Stage 2: Demographic and fiscal calibration</strong> — Household weights
            are adjusted using positive-entropy calibration to match SSA demographic
            and fiscal projections while keeping weights non-negative.
          </p>
          <p className="mt-4">
            <strong>Key innovation:</strong> tax calculations happen at the household level
            before aggregation, which avoids person-to-household mapping inconsistencies.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Positive-Entropy Calibration Method"
          summary="Targets demographics, benefits, payroll, and trust-fund revenues."
        >
          <p>
            <strong>Positive-entropy calibration</strong> simultaneously matches five
            official targets while minimizing divergence from the baseline
            Enhanced CPS household weights. The current `ss-payroll-tob`
            publication profile uses this entropy path; GREG is retained only
            as a legacy flag-based option in the data pipeline.
          </p>
          <BulletList>
            <li><strong>Age distribution</strong> — 86 categories from SSA population projections.</li>
            <li><strong>Social Security benefits</strong> — total OASDI benefit payments.</li>
            <li><strong>Taxable payroll</strong> — earnings subject to Social Security taxation.</li>
            <li><strong>OASDI trust fund revenue</strong> — taxation of benefits revenue to Social Security.</li>
            <li><strong>Medicare HI trust fund revenue</strong> — taxation of benefits revenue to Medicare.</li>
          </BulletList>
          <div className="mt-4 rounded-[var(--pe-radius-container)] border border-[var(--pe-color-primary-200)] bg-[var(--pe-color-primary-50)] px-4 py-3">
            <p>
              <strong>Validation:</strong> release artifacts are checked against the intended
              Trustees calibration contract before they enter the dashboard.
            </p>
          </div>
        </AccordionItem>

        <AccordionItem
          title="Data Sources"
          summary="Calibrated to SSA and CMS projections for demographics, benefits, payroll, and trust-fund revenue."
        >
          <p>
            <strong>Microdata foundation:</strong> Enhanced CPS 2024 from PolicyEngine US with
            IRS integration and machine-learning imputation.
          </p>
          <p className="mt-4">
            <strong>Calibration targets:</strong>
          </p>
          <BulletList>
            <li>Age distribution from SSA single-year demographic projections.</li>
            <li>Social Security benefits from the 2025 Trustees Report.</li>
            <li>Taxable payroll from the 2025 Trustees Report.</li>
            <li>OASDI trust-fund TOB revenue from SSA Trustees supplemental tables.</li>
            <li>Medicare HI trust-fund TOB revenue from the 2025 Medicare Trustees Report.</li>
          </BulletList>
        </AccordionItem>

        <AccordionItem
          title="Scoring Approach"
          summary="Static scoring holds behavior constant; conventional scoring adds labor-supply responses."
        >
          <p>
            <strong>Static scoring:</strong> holds taxpayer behavior constant and isolates the
            mechanical effect of policy changes.
          </p>
          <p className="mt-4">
            <strong>Conventional scoring:</strong> extends the same Trustees baseline lineage
            with age-based labor-supply elasticities for the standard reforms
            `option1` through `option12`.
          </p>
          <p className="mt-4">
            The special-case balanced-fix scenarios `option13` and `option14_stacked` remain
            static-only in the current release. A conventional version would require a separate
            iterative post-response solve rather than the published standard dynamic pipeline.
          </p>
          <p className="mt-4">
            The largest conventional/static differences typically show up in the
            long horizon for the structural swap options and the broad
            tax-expansion options.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Trust Fund Allocation"
          summary="Revenue allocation varies by reform type."
        >
          <BulletList>
            <li><strong>Options 1-2 and 8-10</strong>: current-law style benefit-tax allocation.</li>
            <li><strong>Options 3-4 and 11</strong>: baseline-share allocation.</li>
            <li><strong>Options 5-6</strong>: employer-contribution taxes directed to their trust funds.</li>
            <li><strong>Option 7</strong>: allocated to general revenues.</li>
            <li><strong>Option 12-13</strong>: handled through direct branching or special baseline logic.</li>
          </BulletList>
        </AccordionItem>
      </div>

      <div className="rounded-[var(--pe-radius-feature)] bg-[var(--pe-color-bg-secondary)] px-5 py-4">
        <h3 className="text-base font-semibold text-[var(--pe-color-text-title)]">
          External resources
        </h3>
        <ul className="mt-3 grid gap-x-6 gap-y-1.5 text-sm text-[var(--pe-color-primary-700)] sm:grid-cols-2">
          <li>
            <a href="/paper/" target="_blank" rel="noreferrer" className="hover:underline">
              Citable paper
            </a>
          </li>
          <li>
            <a href="https://www.ssa.gov/oact/tr/2025/" target="_blank" rel="noreferrer" className="hover:underline">
              2025 Social Security Trustees Report
            </a>
          </li>
          <li>
            <a href="https://policyengine.github.io/policyengine-us-data" target="_blank" rel="noreferrer" className="hover:underline">
              PolicyEngine US Data Documentation
            </a>
          </li>
          <li>
            <a href="https://github.com/PolicyEngine/crfb-tob-impacts" target="_blank" rel="noreferrer" className="hover:underline">
              Analysis source code
            </a>
          </li>
        </ul>
      </div>
    </section>
  );
}
