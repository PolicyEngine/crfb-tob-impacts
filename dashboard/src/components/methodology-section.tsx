"use client";

import { useState } from "react";

import { MethodologyDiagram } from "@/components/methodology-diagram";
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
          summary="We build each projection year independently: light demographic reweighting, then value scaling to official aggregates given those weights, then a final exact calibration."
          defaultOpen
        >
          <p>
            We build each projection year from the same 2024 microdata in four
            stages:
          </p>
          <BulletList>
            <li>
              <strong>A. Grow incomes to the target year.</strong> We grow each
              income category with its own index, built on CBO revenue
              projections. After 2034, we cap the growth of dividend,
              partnership and S-corporation income at Trustees nominal GDP
              growth, scaling it down on every record. We leave earnings out of
              the cap and scale them to SSA taxable payroll in Stage C. We index
              tax parameters as statute does through 2034, and from 2035 we
              switch those on the IRS inflation index to PolicyEngine&apos;s
              wage index.
            </li>
            <li>
              <strong>B. Demographic reweight.</strong> We shift household weights
              to the Trustees population in five-year age groups with a light
              positive-entropy adjustment. Weights carry demographics only.
            </li>
            <li>
              <strong>C. Value calibration, given those weights.</strong>{" "}
              Holding the reweighted population fixed, we scale earnings to SSA
              taxable payroll (accounting for the taxable maximum), benefits to
              OASDI cost, and most of beneficiary households&apos; other income
              toward taxation-of-benefits revenue.
            </li>
            <li>
              <strong>D. Final entropy calibration.</strong> We adjust the weights
              a last time to hit the age distribution and all fiscal targets
              exactly, with guard constraints holding investment and other income
              at their totals entering this stage.
            </li>
          </BulletList>
          <p className="mt-4">
            Reweighting alone can match dollar aggregates only by changing the
            population&apos;s makeup, and value scaling alone cannot shift the
            age structure, so we use each for its own channel. We add no records to the
            populace database in any projected dataset.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Calibration targets and publication gates"
          summary="Exact targets for demographics, benefits, payroll, and trust-fund revenues, with sample-quality gates on every projected dataset."
        >
          <p>
            We match every target exactly with <strong>positive-entropy
            calibration</strong>, which keeps all weights positive and minimizes
            divergence from the Stage B weights. The age, benefit, payroll, and
            revenue targets follow the 2026 Trustees Reports&apos; intermediate
            assumptions:
          </p>
          <BulletList>
            <li>
              <strong>Age distribution</strong> — SSA population projections, in
              five-year age groups.
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
              <strong>Income guards</strong> — we hold investment and other
              non-payroll income at their totals entering the final calibration.
            </li>
          </BulletList>
          <div className="mt-4 rounded-[var(--pe-radius-container)] border border-[var(--pe-color-primary-200)] bg-[var(--pe-color-primary-50)] px-4 py-3">
            <p>
              <strong>Gates:</strong> the projection script stops on any year
              that fails its effective sample size or weight concentration
              checks or, from 2075, its taxation-of-benefits contributor support
              checks. Every anchor year clears all of them. The baseline tab
              charts every major series — including uncalibrated by-products
              like income tax and AGI — through 2100, against external references
              where they exist.
            </p>
          </div>
        </AccordionItem>

        <AccordionItem
          title="Data sources"
          summary="We calibrate PolicyEngine's populace microdata to SSA and CMS projections, with income growth from CBO."
        >
          <p>
            <strong>Microdata foundation:</strong> PolicyEngine&apos;s populace
            2024 database, built from primary sources (CPS ASEC, IRS PUF, SCF,
            SIPP, CPS ORG, MEPS, ACS). PolicyEngine flags households that hold
            about half of the database&apos;s weight as IRS PUF clones. Each clone
            either keeps survey demographics and takes its tax detail from the PUF
            or comes from the PUF&apos;s highest-income returns.
          </p>
          <p className="mt-4">
            <strong>Projection targets and inputs:</strong>
          </p>
          <BulletList>
            <li>
              Demographics, payroll, benefits, and GDP from the 2026 Social
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
              Per-category income growth from CBO revenue projections through
              2036 and their last growth rates after that, with a cap at
              Trustees GDP growth after 2034 on dividend, partnership and
              S-corporation income.
            </li>
            <li>
              Wage indexing from PolicyEngine&apos;s own National Average Wage
              Index series, which reaches about 9.1 times its 2033 level by
              2099, against about 10.2 times for the Trustees&apos; average wage
              index.
            </li>
          </BulletList>
          <p className="mt-4">
            The 2026 Trustees Report incorporates the 2025 reconciliation act
            (OBBBA), including the senior deduction, in current law.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Scoring approach"
          summary="We show static scores on the charts and publish labor-supply results in the results file."
        >
          <p>
            <strong>Static scoring:</strong> we hold taxpayer behavior
            constant, so the estimates show the mechanical effect of each policy
            change. We run full microsimulations of all fifteen reforms at
            anchor years: 2026, 2028, 2029, 2030, and every fifth year from 2035 to 2100, plus 2062 for the two Roth swaps. The
            2028 and 2029 anchors bracket the senior deduction&apos;s 2028
            sunset, so the budget window shows that step instead of smoothing
            across it. We interpolate linearly between anchors to a complete
            annual series, which the revenue-over-time chart traces and which we
            sum for the 75-year and present-value totals. We interpolate the
            distributional charts between anchor years and tag each row
            of the results file as an exact anchor or an interpolation.
          </p>
          <p className="mt-4">
            <strong>Supplemental labor-supply response:</strong> we also run full
            microsimulations with labor-supply responses for thirteen of the
            reforms at the 2026 and 2100 endpoints, plus 2062 for the two Roth
            swaps. The charts show static scores, and we publish the
            labor-supply rows in the results file.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Trust fund allocation"
          summary="Revenue allocation varies by reform type."
        >
          <BulletList>
            <li>
              <strong>
                Full repeal; 85%, 90%, 93%, 95%, and 100% taxation; full MAGI
                inclusion; and the 2005 Tax Panel deduction
              </strong>
              : we default to baseline-share allocation, with a toggle for
              current-law allocation.
            </li>
            <li>
              <strong>85% + deduction, $500 credit, and $700 credit</strong>: we
              use baseline-share allocation under both settings.
            </li>
            <li>
              <strong>Roth swap and Phased Roth</strong>: we credit each trust
              fund with the income tax on its own employer contribution, net of the
              benefit-tax revenue it loses.
            </li>
            <li>
              <strong>No senior deduction</strong>: the total equals the full
              federal income-tax gain. We credit each fund with its
              taxation-of-benefits change and assign the rest to the general
              fund.
            </li>
            <li>
              <strong>Reverse Roth</strong>: we count the income-tax cost of
              deducting employee payroll taxes against OASDI and leave
              HI&apos;s benefit-tax share as the model scores it.
            </li>
          </BulletList>
          <p className="mt-4">
            Under the scheduled-benefits baseline, the all-OASDI and all-HI
            toggles assign any reform&apos;s whole impact to one trust fund.
          </p>
        </AccordionItem>

        <AccordionItem
          title="Scoring baselines and present value"
          summary="We score reforms against scheduled benefits or a Social Security solvency baseline and report 75-year totals in present value."
        >
          <BulletList>
            <li>
              <strong>Scheduled benefits:</strong> we score the reform against
              the law as it stands, with Social Security paying full scheduled
              benefits and with inflation-indexed income-tax parameters following
              PolicyEngine&apos;s wage index from 2035.
            </li>
            <li>
              <strong>SS solvent:</strong> we score the reform against a
              baseline that closes Social Security&apos;s long-run shortfall
              through roughly equal benefit reductions and payroll-rate
              increases (a balanced &ldquo;traditional fix&rdquo;), so we
              measure its effect on top of an already-solvent system. We offer
              this baseline for repeal, 85%, 100%, and the Phased Roth; it
              applies from 2035, and we score 2026-2034 against scheduled
              benefits. A reform whose structure differs from current law can
              step at 2035 where the baseline switches &mdash; clearest for the
              Phased Roth &mdash; which the dashed marker on the chart flags.
            </li>
          </BulletList>
          <p className="mt-4">
            <strong>Present value:</strong> for 75-year totals, we discount each
            year&apos;s flow to 2026 at each trust fund&apos;s effective
            interest rates under the Trustees&apos; intermediate assumptions:
            OASDI flows at the rates implied by the compound effective
            trust-fund interest factors in Table VI.G1 of the 2026 OASDI
            Trustees Report, and Medicare HI flows at the effective rates in
            Table IV.A4 of the 2026 Medicare Trustees Report, graded to the
            4.7 percent ultimate nominal rate by 2040. General-fund flows and
            economy-wide denominators use the OASDI series, and we sum the
            discounted components into the 75-year total. We show ten-year
            budget-window totals in nominal dollars.
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
    </section>
  );
}
