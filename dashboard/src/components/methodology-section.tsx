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
    <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white shadow-[0_18px_48px_rgba(16,24,40,0.06)]">
      <button
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full items-start justify-between gap-4 px-5 py-5 text-left"
        aria-expanded={isOpen}
      >
        <div>
          <h3 className="text-lg font-semibold text-[var(--pe-color-text-title)]">
            {title}
          </h3>
          <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
            {summary}
          </p>
        </div>
        <span className="mt-1 text-[var(--pe-color-text-tertiary)]">
          {isOpen ? "−" : "+"}
        </span>
      </button>
      {isOpen ? (
        <div className="border-t border-[var(--pe-color-border-light)] px-5 py-5 text-sm leading-7 text-[var(--pe-color-text-secondary)]">
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
    <section className="space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--pe-color-text-tertiary)]">
          Methodology
        </p>
        <h2 className="mt-2 text-2xl font-semibold text-[var(--pe-color-text-title)]">
          Methods and external resources
        </h2>
      </div>

      <MethodologyDiagram />

      <div className="space-y-4">
        <AccordionItem
          title="Two-Stage Projection Methodology"
          summary="75-year projections use economic uprating followed by GREG demographic calibration to match Trustees Report targets."
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
            <strong>Stage 2: Demographic Calibration</strong> — Household weights are adjusted
            using GREG calibration to match SSA demographic and fiscal projections.
          </p>
          <p className="mt-4">
            <strong>Key innovation:</strong> tax calculations happen at the household level
            before aggregation, which avoids person-to-household mapping inconsistencies.
          </p>
        </AccordionItem>

        <AccordionItem
          title="GREG Calibration Method"
          summary="Targets demographics, benefits, payroll, and trust-fund revenues."
        >
          <p>
            <strong>GREG calibration</strong> simultaneously matches five official targets.
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
              <strong>Validation:</strong> the original dashboard claimed all calibration targets
              were achieved within 0.1% of SSA and CMS projections across the 75-year horizon.
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
            <strong>Conventional scoring:</strong> incorporates labor-supply elasticities based
            on CBO estimates, with older workers receiving larger responses in the historical stack.
          </p>
          <p className="mt-4">
            The biggest conventional/static differences typically show up for Roth-style swap options.
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

      <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-5 shadow-[0_18px_48px_rgba(16,24,40,0.06)]">
        <h3 className="text-lg font-semibold text-[var(--pe-color-text-title)]">
          External resources
        </h3>
        <ul className="mt-4 space-y-3 text-sm text-[var(--pe-color-primary-700)]">
          <li>
            <a href="https://www.ssa.gov/oact/tr/2025/" target="_blank" rel="noreferrer">
              2025 Social Security Trustees Report
            </a>
          </li>
          <li>
            <a href="https://policyengine.github.io/policyengine-us-data" target="_blank" rel="noreferrer">
              PolicyEngine US Data Documentation
            </a>
          </li>
          <li>
            <a href="https://github.com/PolicyEngine/crfb-tob-impacts" target="_blank" rel="noreferrer">
              Analysis source code
            </a>
          </li>
        </ul>
      </div>
    </section>
  );
}
