"use client";

import { useState } from "react";

import { MethodologyDiagram } from "@/components/methodology-diagram";
import { LiveModelingProgress } from "@/components/live-modeling-progress";
import { ReproducibilityRoadmap } from "@/components/reproducibility-roadmap";
import { sitePath } from "@/lib/site-path";

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
  const paperHref = sitePath("/paper/");

  return (
    <section className="space-y-4 border-t border-[var(--pe-color-border-light)] pt-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
          Methods and sources
        </h2>
        <p className="mt-2 text-sm text-[var(--pe-color-text-secondary)]">
          Summary methodology. See the{" "}
          <a
            href={paperHref}
            target="_blank"
            rel="noreferrer"
            className="text-[var(--pe-color-primary-700)] hover:underline"
          >
            citable paper
          </a>{" "}
          for the full methodology and bibliography.
        </p>
      </div>

      <MethodologyDiagram />

      <div className="space-y-4">
        <AccordionItem
          title="Yearly calibration: demographics in weights, economics in values"
          summary="Each projection year is built independently: light demographic reweighting, then value scaling to official aggregates given those weights, then a final exact calibration."
          defaultOpen
        >
          <p>
            Every year from 2026 to 2100 is constructed from the same 2024
            microdata in four stages:
          </p>
          <BulletList>
            <li>
              <strong>A. Grow incomes to the target year.</strong> Each income
              category follows its own uprating path — CBO-vintage growth
              through 2034, capped at the Trustees nominal GDP path beyond so no
              source outruns the projected economy. Tax parameters follow
              statutory indexing.
            </li>
            <li>
              <strong>B. Demographic reweight.</strong> A light positive-entropy
              adjustment shifts household weights to the Trustees single-year
              age distribution. Weights carry demographics only — they are not
              asked to fix dollar aggregates.
            </li>
            <li>
              <strong>C. Value calibration, given those weights.</strong>{" "}
              Scalars solved against the reweighted population align earnings
              with SSA taxable payroll (accounting for the taxable maximum),
              benefits with OASDI cost, and beneficiary non-benefit income with
              taxation-of-benefits revenue.
            </li>
            <li>
              <strong>D. Final entropy calibration.</strong> A last weight
              adjustment hits the age distribution and all fiscal targets
              exactly, with guard constraints holding investment and other
              income to their growth paths.
            </li>
          </BulletList>
          <p className="mt-4">
            Separating the channels keeps both honest: reweighting alone would
            hit aggregates by silently distorting who the population is, while
            value scaling alone could not shift the age structure. Every record
            in every published year is a real survey household — no synthetic
            rows. A clone-free build of 2100, the hardest year, passes every
            publication gate with a comfortable margin, so the populace base
            supports the full horizon bare.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Calibration targets and publication gates"
          summary="Exact targets for demographics, benefits, payroll, and trust-fund revenues, with sample-quality gates on every published year."
        >
          <p>
            <strong>Positive-entropy calibration</strong> matches every target
            exactly while minimizing divergence from the base survey weights and
            keeping all weights positive. Targets come from the 2026 Trustees
            Report intermediate assumptions:
          </p>
          <BulletList>
            <li>
              <strong>Age distribution</strong> — single-year SSA population
              projections.
            </li>
            <li>
              <strong>Social Security benefits</strong> — total OASDI program
              cost.
            </li>
            <li>
              <strong>Taxable payroll</strong> — earnings subject to Social
              Security taxation.
            </li>
            <li>
              <strong>OASDI trust fund revenue</strong> — taxation of benefits
              revenue to Social Security.
            </li>
            <li>
              <strong>Medicare HI trust fund revenue</strong> — taxation of
              benefits revenue to Medicare.
            </li>
            <li>
              <strong>Income guards</strong> — investment and other non-payroll
              income held to their uprated paths.
            </li>
          </BulletList>
          <div className="mt-4 rounded-[var(--pe-radius-container)] border border-[var(--pe-color-primary-200)] bg-[var(--pe-color-primary-50)] px-4 py-3">
            <p>
              <strong>Gates:</strong> a year publishes only if it passes
              effective sample size, weight concentration, and
              taxation-of-benefits contributor support checks. The baseline tab
              charts every major series — including uncalibrated by-products
              like income tax and AGI — against external references through
              2100.
            </p>
          </div>
        </AccordionItem>

        <AccordionItem
          title="Data sources"
          summary="populace microdata calibrated to SSA, CMS, and CBO projections."
        >
          <p>
            <strong>Microdata foundation:</strong> PolicyEngine&apos;s populace
            2024 database, built entirely from primary sources (CPS ASEC, IRS
            PUF, SCF, SIPP, CPS ORG, MEPS, ACS) with every layer traceable to
            its origin.
          </p>
          <p className="mt-4">
            <strong>Projection targets:</strong>
          </p>
          <BulletList>
            <li>
              Demographics, payroll, benefits, GDP, and AWI from the 2026 Social
              Security Trustees Report intermediate assumptions.
            </li>
            <li>
              OASDI taxation-of-benefits revenue from the Trustees income-rate
              and payroll tables.
            </li>
            <li>
              Medicare HI taxation-of-benefits revenue from the CMS 2026
              Trustees expanded tables, annual through 2100.
            </li>
            <li>
              Per-category income growth from the CBO long-term forecast through
              2034, capped at Trustees GDP growth thereafter.
            </li>
          </BulletList>
          <p className="mt-4">
            The 2026 Trustees Report incorporates the 2025 reconciliation act
            (OBBBA), including the senior deduction, directly in current law —
            no post-legislation bridge is required.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Scoring approach"
          summary="Static scoring is primary; behavioral labor-response results are supplemental."
        >
          <p>
            <strong>Static scoring:</strong> holds taxpayer behavior constant
            and isolates the mechanical effect of policy changes. This is the
            dashboard&apos;s default scoring surface. All fourteen reforms are
            computed from full reform H5 microsimulation at anchor years — 2026,
            2028, 2029, 2030, and every fifth year from 2035 to 2100, with 2032
            and 2033 added for the employer-payroll Roth option. The 2028 and
            2029 anchors bracket the senior deduction&apos;s 2028 sunset so the
            budget window reflects that step rather than smoothing across it.
            Intermediate years are linearly interpolated to a complete annual
            series, which is what the revenue-over-time chart traces and what
            the 75-year and present-value totals aggregate; the distributional
            charts interpolate between the same anchor years. Each row is tagged
            as an exact anchor or an interpolated fill, and the exact
            anchor-year H5 rows are preserved in the production results.
          </p>
          <p className="mt-4">
            <strong>Supplemental labor-supply response:</strong> uses the same
            full reform H5 lineage at the 2026 and 2100 endpoints and is
            available from the Scoring control.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Trust fund allocation"
          summary="Revenue allocation varies by reform type."
        >
          <BulletList>
            <li>
              <strong>Options 1-2 and 8-10</strong>: default to baseline-share
              allocation, with toggles for current-law, all-OASDI, and all-HI
              allocation.
            </li>
            <li>
              <strong>Options 3-4 and 11</strong>: use baseline-share
              allocation.
            </li>
            <li>
              <strong>Options 5-6</strong>: employer-contribution taxes directed
              to their trust funds.
            </li>
            <li>
              <strong>Option 7</strong>: total is the full federal income-tax
              gain; OASDI, HI, and general fund show the accounting split.
            </li>
            <li>
              <strong>Option 12</strong>: handled through direct branching for
              the structural swap.
            </li>
          </BulletList>
        </AccordionItem>

        <AccordionItem
          title="Scoring baselines and present value"
          summary="Reforms can be scored against scheduled benefits or a Social Security solvency baseline; 75-year totals are reported in present value."
        >
          <BulletList>
            <li>
              <strong>Scheduled benefits:</strong> the reform is scored against
              the law as it stands, with Social Security paying full scheduled
              benefits, including the Trustees long-run taxation-of-benefits
              thresholds.
            </li>
            <li>
              <strong>SS solvent:</strong> the reform is scored against a
              baseline that closes Social Security&apos;s long-run shortfall
              through roughly equal benefit reductions and payroll-rate
              increases (a balanced &ldquo;traditional fix&rdquo;), so its
              effect is measured on top of an already-solvent system. Available
              for repeal, 85%, 100%, and the Phased Roth; the solvent baseline
              applies from 2035, with 2026-2034 scored against scheduled
              benefits. A reform whose structure differs from current law can
              step at 2035 where the baseline switches &mdash; clearest for the
              Phased Roth &mdash; which the dashed marker on the chart flags.
            </li>
          </BulletList>
          <p className="mt-4">
            <strong>Present value:</strong> 75-year totals discount each
            year&apos;s flow to 2026 at each trust fund&apos;s effective
            interest rates under the Trustees&apos; intermediate assumptions:
            OASDI flows at the rates implied by the compound effective
            trust-fund interest factors in Table VI.G1 of the 2026 OASDI
            Trustees Report, and Medicare HI flows at the effective rates in
            Table IV.A4 of the 2026 Medicare Trustees Report, graded to the
            4.7 percent ultimate nominal rate by 2040. General-fund flows and
            economy-wide denominators use the OASDI series, and the 75-year
            total is the sum of the discounted components. Ten-year
            budget-window totals are shown in nominal dollars.
          </p>
        </AccordionItem>
      </div>

      <div className="rounded-[var(--pe-radius-feature)] bg-[var(--pe-color-bg-secondary)] px-5 py-4">
        <h3 className="text-base font-semibold text-[var(--pe-color-text-title)]">
          External resources
        </h3>
        <ul className="mt-3 grid gap-x-6 gap-y-1.5 text-sm text-[var(--pe-color-primary-700)] sm:grid-cols-2">
          <li>
            <a
              href={paperHref}
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              Citable paper
            </a>
          </li>
          <li>
            <a
              href="https://www.ssa.gov/oact/tr/2026/"
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              2026 Social Security Trustees Report
            </a>
          </li>
          <li>
            <a
              href="https://huggingface.co/datasets/policyengine/populace-us"
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              populace microdata
            </a>
          </li>
          <li>
            <a
              href="https://policyengine.github.io/policyengine-us-data"
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              PolicyEngine US Data Documentation
            </a>
          </li>
          <li>
            <a
              href="https://github.com/PolicyEngine/crfb-tob-impacts"
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              Analysis source code
            </a>
          </li>
        </ul>
      </div>

      <div className="grid gap-4 border-t border-[var(--pe-color-border-light)] pt-6 lg:grid-cols-[12rem_minmax(0,1fr)]">
        <div>
          <p className="text-xs font-semibold uppercase tracking-normal text-[var(--pe-color-text-tertiary)]">
            Appendix
          </p>
          <p className="mt-1 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
            Internal production tracking
          </p>
        </div>
        <div className="space-y-4">
          <details className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
            <summary className="cursor-pointer px-5 py-4 text-left">
              <span className="block text-base font-semibold text-[var(--pe-color-text-title)]">
                Internal reproducibility roadmap
              </span>
              <span className="mt-1 block text-sm leading-6 text-[var(--pe-color-text-secondary)]">
                Gates, logs, and artifact targets for the CRFB rebuild workflow.
              </span>
            </summary>
            <div className="border-t border-[var(--pe-color-border-light)]">
              <ReproducibilityRoadmap embedded />
            </div>
          </details>
          <details className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
            <summary className="cursor-pointer px-5 py-4 text-left">
              <span className="block text-base font-semibold text-[var(--pe-color-text-title)]">
                Live modeling status
              </span>
              <span className="mt-1 block text-sm leading-6 text-[var(--pe-color-text-secondary)]">
                Baseline readiness and full-H5 reform artifact progress.
              </span>
            </summary>
            <div className="border-t border-[var(--pe-color-border-light)]">
              <LiveModelingProgress />
            </div>
          </details>
        </div>
      </div>
    </section>
  );
}
