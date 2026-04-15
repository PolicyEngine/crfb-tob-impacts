"use client";

import { motion } from "framer-motion";
import { Download, ExternalLink, FileText } from "lucide-react";
import type { ReactNode } from "react";

const sectionLinks = [
  ["scope", "Scope"],
  ["policy-design", "Policy design"],
  ["methods", "Data and methods"],
  ["validation-results", "Validation and results"],
  ["publication", "Publication boundary"],
  ["sources", "Sources"],
];

const tenYearRows = [
  ["option1", "-1,974.2"],
  ["option13", "-24.2"],
  ["option7", "+75.0"],
  ["option3", "+89.5"],
  ["option4", "+184.5"],
  ["option11", "+230.9"],
  ["option2", "+357.1"],
  ["option5", "+409.5"],
  ["option14_stacked", "+440.9"],
  ["option9", "+529.0"],
  ["option10", "+703.4"],
  ["option8", "+880.0"],
  ["option6", "+1,295.8"],
  ["option12", "+2,197.2"],
];

const milestoneRows = [
  ["option1", "-257.5", "-507.4", "-1,503.2", "-3,862.8"],
  ["option2", "+43.1", "+47.0", "+99.9", "+222.8"],
  ["option4", "+12.9", "+11.5", "+51.6", "+168.3"],
  ["option5", "+40.9", "+17.3", "-155.7", "-338.5"],
  ["option6", "+184.1", "+17.3", "-155.7", "-338.5"],
  ["option8", "+109.8", "+169.3", "+451.3", "+1,138.0"],
  ["option10", "+87.2", "+128.1", "+335.7", "+825.9"],
  ["option12", "+243.2", "+175.2", "-155.7", "-338.5"],
  ["option13", "-24.2", "-59.6", "-247.3", "-682.9"],
  ["option14_stacked", "+440.9", "-334.3", "-5,219.8", "-23,120.5"],
];

const dynamicRows = [
  ["option1", "-1,875.4", "+98.8"],
  ["option7", "+74.5", "-0.4"],
  ["option4", "+189.2", "+4.7"],
  ["option11", "+230.7", "-0.2"],
  ["option5", "+234.6", "-174.9"],
  ["option2", "+361.8", "+4.7"],
  ["option9", "+527.6", "-1.4"],
  ["option10", "+697.0", "-6.3"],
  ["option8", "+867.4", "-12.6"],
  ["option6", "+1,121.8", "-174.0"],
  ["option12", "+1,929.9", "-267.3"],
];

const specialCaseRows = [
  ["option13", "2035", "-24.2", "-24.2", "+479.8", "+155.6"],
  ["option13", "2050", "-59.6", "-59.6", "+972.0", "+259.0"],
  ["option13", "2075", "-247.3", "-247.3", "+3,488.4", "+290.3"],
  ["option13", "2100", "-682.9", "-682.9", "+7,815.1", "-1,044.6"],
  ["option14_stacked", "2035", "+440.9", "-31.0", "+194.7", "+77.7"],
  ["option14_stacked", "2050", "-334.3", "-289.9", "+162.7", "+77.2"],
  ["option14_stacked", "2075", "-5,219.8", "-1,255.9", "+359.1", "-261.7"],
  ["option14_stacked", "2100", "-23,120.5", "-3,179.9", "+941.8", "-581.0"],
];

function PaperSection({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <motion.section
      id={id}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="scroll-mt-24 border-t border-[var(--pe-color-border-light)] pt-10"
    >
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--pe-color-text-tertiary)]">
        {eyebrow}
      </p>
      <h2 className="mt-3 max-w-3xl text-3xl font-semibold tracking-[-0.035em] text-[var(--pe-color-text-title)]">
        {title}
      </h2>
      <div className="mt-6 space-y-5 text-base leading-8 text-[var(--pe-color-text-secondary)]">
        {children}
      </div>
    </motion.section>
  );
}

function BulletList({ children }: { children: ReactNode }) {
  return (
    <ul className="ml-5 list-disc space-y-2 text-[var(--pe-color-text-secondary)]">
      {children}
    </ul>
  );
}

function Callout({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-primary-200)] bg-[var(--pe-color-primary-50)] px-5 py-4">
      <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--pe-color-primary-800)]">
        {title}
      </h3>
      <div className="mt-3 text-sm leading-7 text-[var(--pe-color-text-secondary)]">
        {children}
      </div>
    </div>
  );
}

function PaperTable({
  title,
  columns,
  rows,
}: {
  title: string;
  columns: string[];
  rows: string[][];
}) {
  return (
    <div className="overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
      <div className="bg-[var(--pe-color-bg-secondary)] px-5 py-3">
        <h3 className="text-sm font-semibold text-[var(--pe-color-text-title)]">
          {title}
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-[var(--pe-color-border-light)] text-sm">
          <thead className="text-[var(--pe-color-text-secondary)]">
            <tr>
              {columns.map((column, index) => (
                <th
                  key={column}
                  className={`px-5 py-3 font-medium ${
                    index === 0 ? "text-left" : "text-right"
                  }`}
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--pe-color-border-light)]">
            {rows.map((row) => (
              <tr key={row.join("-")}>
                {row.map((cell, index) => (
                  <td
                    key={`${row[0]}-${cell}-${index}`}
                    className={`px-5 py-3 ${
                      index === 0
                        ? "font-medium text-[var(--pe-color-text-primary)]"
                        : "text-right tabular-nums text-[var(--pe-color-text-secondary)]"
                    }`}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 text-[var(--pe-color-primary-700)] transition hover:text-[var(--pe-color-primary-800)] hover:underline"
    >
      {children}
      <ExternalLink className="h-3.5 w-3.5" />
    </a>
  );
}

export function PaperTab() {
  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_18rem]">
      <article className="min-w-0 rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-6 shadow-[0_18px_48px_rgba(16,24,40,0.06)] sm:px-8 lg:px-10">
        <header className="border-b border-[var(--pe-color-border-light)] pb-8">
          <div className="flex items-center gap-3 text-[var(--pe-color-primary-700)]">
            <FileText className="h-5 w-5" />
            <p className="text-xs font-semibold uppercase tracking-[0.22em]">
              Citable manuscript
            </p>
          </div>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-[-0.045em] text-[var(--pe-color-text-title)] sm:text-5xl">
            Social Security taxation reform
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-[var(--pe-color-text-secondary)]">
            Long-run policy analysis and impact assessment for the current
            CRFB taxation-of-benefits reform package, integrated into the same
            themed surface as the interactive dashboard.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a
              href="/paper/index.pdf"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-full bg-[var(--pe-color-primary-600)] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--pe-color-primary-700)]"
            >
              <Download className="h-4 w-4" />
              Download PDF
            </a>
            <a
              href="/paper/"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-full border border-[var(--pe-color-border-medium)] px-4 py-2.5 text-sm font-medium text-[var(--pe-color-text-primary)] transition hover:border-[var(--pe-color-primary-300)] hover:text-[var(--pe-color-primary-700)]"
            >
              Standalone paper
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </header>

        <div className="space-y-12">
          <PaperSection id="scope" eyebrow="01" title="Scope and framing">
            <p>
              This manuscript is the long-form publication layer for the
              Social Security taxation-of-benefits project. It sits alongside
              the live dashboard, which is the current-results explorer, and
              the operational docs, which track rerun status, reproducibility,
              and audit decisions.
            </p>
            <p>
              The current analysis extends the original eight-option report to
              a broader fourteen-scenario package over the 2026-2100 modeling
              window: standard reforms option1 through option12, option13 as a
              balanced-fix baseline beginning in 2035, and option14_stacked as
              a structural reform layered on top of that balanced-fix baseline.
            </p>
            <Callout title="Current-law baseline">
              <p>
                Current law taxes Social Security benefits once combined
                income exceeds statutory thresholds, with up to 50 percent of
                benefits taxable at the lower tier and up to 85 percent taxable
                at the higher tier. The baseline also reflects the temporary
                bonus senior deduction enacted in OBBBA and its scheduled
                expiration after 2028.
              </p>
            </Callout>
            <div className="grid gap-5 lg:grid-cols-2">
              <div>
                <h3 className="text-base font-semibold text-[var(--pe-color-text-title)]">
                  Research questions
                </h3>
                <BulletList>
                  <li>How do alternative reforms alter trust-fund revenue, household tax burdens, and long-run fiscal outcomes?</li>
                  <li>What validation framework makes 2026-2100 microsimulation estimates interpretable?</li>
                  <li>How should the dashboard, paper, and audit record relate without drifting?</li>
                </BulletList>
              </div>
              <div>
                <h3 className="text-base font-semibold text-[var(--pe-color-text-title)]">
                  Why keep a manuscript
                </h3>
                <BulletList>
                  <li>Preserves the source and benchmark trail from the first report.</li>
                  <li>Carries fuller methods exposition than the live app should contain.</li>
                  <li>Supports SSRN-style circulation and external citation.</li>
                  <li>Freezes narrative interpretation while the dashboard evolves.</li>
                </BulletList>
              </div>
            </div>
          </PaperSection>

          <PaperSection id="policy-design" eyebrow="02" title="Policy design">
            <p>
              The reform menu spans direct benefit-taxation changes,
              senior-relief redesigns, and employer-payroll-tax swaps. The
              standard series shares a common current-law baseline; the
              balanced-fix special cases intentionally do not.
            </p>
            <div className="grid gap-5 lg:grid-cols-3">
              <Callout title="Direct taxability">
                <p>
                  Options 1, 2, 8, 9, and 10 change the taxable-benefit base by
                  repealing benefit taxation or applying broader inclusion rates
                  from 85 percent to 100 percent.
                </p>
              </Callout>
              <Callout title="Senior relief">
                <p>
                  Options 3, 4, 7, and 11 extend, repeal, or replace the
                  temporary bonus senior deduction with targeted deduction or
                  credit designs.
                </p>
              </Callout>
              <Callout title="Structural swaps">
                <p>
                  Options 5, 6, and 12 tax employer payroll-tax contributions
                  immediately while phasing down benefit taxation in different
                  ways.
                </p>
              </Callout>
            </div>
            <p>
              Option13 is a stylized solvency baseline beginning in 2035. It
              combines proportional Social Security benefit reductions with
              Social Security and Medicare payroll-tax increases. Option14_stacked
              applies a structural reform on top of that baseline, so its
              results must be interpreted relative to the balanced-fix lineage
              rather than plain current law.
            </p>
          </PaperSection>

          <PaperSection id="methods" eyebrow="03" title="Data and methods">
            <p>
              The analysis uses PolicyEngine US microsimulation with long-run
              projected microdata derived from the Enhanced CPS. The long-run
              pipeline uses economic uprating followed by demographic and
              fiscal calibration so household-level tax logic remains intact
              while aggregate results match official targets.
            </p>
            <div className="grid gap-5 lg:grid-cols-2">
              <div>
                <h3 className="text-base font-semibold text-[var(--pe-color-text-title)]">
                  Calibration targets
                </h3>
                <BulletList>
                  <li>Single-year age population counts from SSA projections.</li>
                  <li>OASDI benefit totals from the 2025 Trustees Report.</li>
                  <li>Social Security taxable payroll from the 2025 Trustees Report.</li>
                  <li>OASDI and HI taxation-of-benefits revenue targets.</li>
                </BulletList>
              </div>
              <div>
                <h3 className="text-base font-semibold text-[var(--pe-color-text-title)]">
                  Current rerun contract
                </h3>
                <BulletList>
                  <li>Target source: trustees_2025_current_law.</li>
                  <li>Calibration profile: ss-payroll-tob.</li>
                  <li>Tax assumption: trustees-core-thresholds-v1.</li>
                  <li>Exact-calibration-only acceptance for delivered years.</li>
                  <li>Pinned local worktrees for policyengine-us and policyengine-us-data.</li>
                </BulletList>
              </div>
            </div>
            <p>
              Static scoring isolates mechanical tax and trust-fund effects.
              Conventional dynamic scoring uses the same baseline lineage and
              layers in labor-supply responses using age-based elasticities for
              standard reforms option1 through option12.
            </p>
            <Callout title="Dynamic scope">
              <p>
                The public dynamic release excludes option13 and
                option14_stacked. Those special cases would require a separate
                iterative balanced-fix solve after behavioral response, which
                was outside the current release contract.
              </p>
            </Callout>
            <div>
              <h3 className="text-base font-semibold text-[var(--pe-color-text-title)]">
                Validation ladder
              </h3>
              <BulletList>
                <li>Dataset metadata validation against the intended Trustees contract.</li>
                <li>Exact-calibration coverage checks for delivered years.</li>
                <li>Sentinel rescoring in representative early, middle, and late years.</li>
                <li>Comparison against known legacy anomalies to confirm they do not reappear.</li>
                <li>Special-case verification for option13 and option14_stacked.</li>
              </BulletList>
            </div>
          </PaperSection>

          <PaperSection id="validation-results" eyebrow="04" title="Validation and results">
            <p>
              The rebuilt static release is a unified Trustees-lineage package
              for all fourteen scenarios. The dashboard and comparison
              spreadsheet draw from the same rebuilt static artifact set, while
              dynamic behavioral results remain a separate standard-panel
              track.
            </p>
            <PaperTable
              title="Ten-year static revenue impacts, 2026-2035 ($B)"
              columns={["Reform", "Revenue impact"]}
              rows={tenYearRows}
            />
            <PaperTable
              title="Milestone static revenue impacts ($B)"
              columns={["Reform", "2035", "2050", "2075", "2100"]}
              rows={milestoneRows}
            />
            <PaperTable
              title="Ten-year dynamic revenue effects, standard panel ($B)"
              columns={["Reform", "Dynamic", "Dynamic minus static"]}
              rows={dynamicRows}
            />
            <PaperTable
              title="Balanced-fix and stacked special cases"
              columns={["Reform", "Year", "Revenue", "TOB", "OASDI net", "HI net"]}
              rows={specialCaseRows}
            />
            <Callout title="Validation status">
              <p>
                The standard static panel was rebuilt on the clean exact
                Trustees contract and cleared late-horizon anomaly checks. The
                standard dynamic panel has complete 2026-2100 recovery for
                option1 through option12. The special-case static panel has
                recovered 2035-2100 artifacts for option13 and option14_stacked.
              </p>
            </Callout>
          </PaperSection>

          <PaperSection id="publication" eyebrow="05" title="Publication boundary">
            <p>
              The repo now has three distinct publication roles: the dashboard
              for current results exploration, the citable manuscript for
              narrative interpretation and methods, and the operational docs for
              audit provenance and rerun decisions.
            </p>
            <div className="grid gap-5 lg:grid-cols-3">
              <Callout title="Dashboard">
                <p>
                  Reform-level comparison, current static and dynamic outputs,
                  special-case baseline views, and downloadable current data.
                </p>
              </Callout>
              <Callout title="Paper">
                <p>
                  SSRN-style circulation, CRFB citation, methods exposition,
                  benchmark framing, appendices, and bibliography.
                </p>
              </Callout>
              <Callout title="Operations">
                <p>
                  Reproducibility details, audit findings, launch identifiers,
                  recovery notes, and delivery rules.
                </p>
              </Callout>
            </div>
            <p>
              For the current static package, the standard panel and
              special-case panel have satisfied the release discipline. For the
              dynamic package, the public release surface is narrower: standard
              dynamic reforms are included, while special-case dynamic scenarios
              remain intentionally excluded.
            </p>
          </PaperSection>

          <PaperSection id="sources" eyebrow="06" title="Sources and reference trail">
            <p>
              The in-tool paper preserves the same source spine as the
              standalone manuscript. The full bibliography is available in the
              citable PDF and standalone paper.
            </p>
            <div className="grid gap-3 text-sm leading-7 sm:grid-cols-2">
              <SourceLink href="https://www.ssa.gov/oact/tr/2025/">
                2025 Social Security Trustees Report
              </SourceLink>
              <SourceLink href="https://www.cms.gov/oact/tr/">
                Medicare Trustees Reports
              </SourceLink>
              <SourceLink href="https://www.irs.gov/publications/p915">
                IRS Publication 915
              </SourceLink>
              <SourceLink href="https://www.cbo.gov/publication/60557">
                CBO Social Security options
              </SourceLink>
              <SourceLink href="https://www.taxfoundation.org/">
                Tax Foundation benchmark estimates
              </SourceLink>
              <SourceLink href="https://policyengine.github.io/policyengine-us-data/">
                PolicyEngine US data documentation
              </SourceLink>
              <SourceLink href="https://github.com/PolicyEngine/crfb-tob-impacts">
                Analysis source repository
              </SourceLink>
              <SourceLink href="/paper/">
                Full standalone paper
              </SourceLink>
            </div>
          </PaperSection>
        </div>
      </article>

      <aside className="hidden xl:block">
        <div className="sticky top-4 rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-5 shadow-[0_18px_48px_rgba(16,24,40,0.06)]">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--pe-color-text-tertiary)]">
            Paper contents
          </p>
          <nav className="mt-4 space-y-1">
            {sectionLinks.map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="block rounded-[var(--pe-radius-element)] px-3 py-2 text-sm text-[var(--pe-color-text-secondary)] transition hover:bg-[var(--pe-color-bg-secondary)] hover:text-[var(--pe-color-text-primary)]"
              >
                {label}
              </a>
            ))}
          </nav>
          <div className="mt-5 border-t border-[var(--pe-color-border-light)] pt-4 text-sm leading-6 text-[var(--pe-color-text-tertiary)]">
            Use the PDF for formal citation. Use this tab for themed reading
            alongside the interactive outputs.
          </div>
        </div>
      </aside>
    </div>
  );
}
