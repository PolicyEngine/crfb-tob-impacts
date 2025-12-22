import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MethodologyDiagram } from './MethodologyDiagram'

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
        clipRule="evenodd"
      />
    </svg>
  )
}

interface AccordionItemProps {
  title: string
  summary: string
  children: React.ReactNode
  defaultOpen?: boolean
}

function AccordionItem({ title, summary, children, defaultOpen = false }: AccordionItemProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="accordion-item">
      <button
        className="accordion-header"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <div className="accordion-header-content">
          <h3>{title}</h3>
          <p className="accordion-summary">{summary}</p>
        </div>
        <ChevronIcon className={`accordion-icon ${isOpen ? 'open' : ''}`} />
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div className="accordion-content">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function MethodologySection() {
  return (
    <section className="methodology-section">
      <h2>Methodology</h2>

      <MethodologyDiagram />

      <div className="methodology-content" style={{ display: 'block' }}>
        <AccordionItem
          title="Two-Stage Projection Methodology"
          summary="75-year projections use economic uprating (Stage 1) followed by GREG demographic calibration (Stage 2) to match SSA Trustees Report targets."
          defaultOpen
        >
          <p>
            <strong>Stage 1: Economic Uprating</strong> — PolicyEngine projects each household's
            economic circumstances forward using official macroeconomic assumptions from the
            2025 Social Security Trustees Report:
          </p>
          <ul>
            <li>Employment income follows wage growth (AWI) projections</li>
            <li>Social Security benefits follow COLA projections</li>
            <li>Capital gains follow asset appreciation projections</li>
            <li>Tax parameters are uprated according to statutory indexing rules (typically CPI-U)</li>
          </ul>
          <p>
            <strong>Stage 2: Demographic Calibration</strong> — Household weights are adjusted
            using GREG calibration to match SSA demographic and fiscal projections. This
            reweighting ensures the synthetic population reflects the target year's age
            distribution and aggregate fiscal totals.
          </p>
          <p>
            <strong>Key Innovation:</strong> By performing all tax calculations at the household
            level before aggregation, this approach avoids person-to-household mapping
            inconsistencies that arise in traditional methods.
          </p>
        </AccordionItem>

        <AccordionItem
          title="GREG Calibration Method"
          summary="Achieves <0.1% error on five calibration targets: demographics, benefits, payroll, and trust fund revenues."
        >
          <p>
            <strong>GREG (Generalized Regression)</strong> calibration simultaneously matches
            five calibration targets from official government projections:
          </p>
          <ul>
            <li>
              <strong>Age Distribution</strong> — 86 categories (ages 0–84 individually, 85+
              aggregated) from SSA population projections.
            </li>
            <li>
              <strong>Social Security Benefits</strong> — Total OASDI benefit payments in
              nominal dollars.
            </li>
            <li>
              <strong>Taxable Payroll</strong> — Total earnings subject to Social Security
              taxation, accounting for the annual wage base cap.
            </li>
            <li>
              <strong>OASDI Trust Fund Revenue</strong> — Taxation of benefits revenue
              allocated to Social Security (Tier 1: first 50% of taxable benefits).
            </li>
            <li>
              <strong>Medicare HI Trust Fund Revenue</strong> — Taxation of benefits revenue
              allocated to Medicare (Tier 2: additional 35% of taxable benefits).
            </li>
          </ul>
          <div className="validation-callout">
            <p>
              <strong>Validation:</strong> All calibration targets achieved within 0.1% of
              SSA and CMS projections across the 75-year horizon.
            </p>
          </div>
        </AccordionItem>

        <AccordionItem
          title="Data Sources"
          summary="Calibrated to SSA and CMS Trustees Report projections for demographics, benefits, payroll, and trust fund revenues."
        >
          <p>
            <strong>Microdata Foundation:</strong> Enhanced CPS 2024 from PolicyEngine US,
            integrating IRS tax records and machine learning imputation (quantile regression
            forests) for accurate income distributions.
          </p>
          <p>
            <strong>Calibration Targets:</strong> GREG calibration matches five aggregate
            targets from official government projections:
          </p>
          <ul>
            <li>
              <strong>Age distribution</strong> — 86 categories from SSA Single Year Age
              Demographic Projections (2024 publication)
            </li>
            <li>
              <strong>Social Security benefits</strong> — Total OASDI payments from SSA 2025
              Trustees Report
            </li>
            <li>
              <strong>Taxable payroll</strong> — Earnings subject to Social Security taxation
              from SSA 2025 Trustees Report
            </li>
            <li>
              <strong>OASDI trust fund revenue</strong> — Calculated from SSA 2025 Trustees
              Report (taxation rate × taxable payroll)
            </li>
            <li>
              <strong>Medicare HI trust fund revenue</strong> — Direct projections from CMS
              2025 Medicare Trustees Report
            </li>
          </ul>
        </AccordionItem>

        <AccordionItem
          title="Scoring Approach"
          summary="Static scoring holds behavior constant; conventional scoring incorporates CBO labor supply elasticities (doubled for 65+)."
        >
          <p>
            <strong>Static Scoring:</strong> Holds taxpayer behavior constant, isolating the
            direct mechanical effect of policy changes. This is the baseline estimate for all
            reform options.
          </p>
          <p>
            <strong>Conventional Scoring (with Labor Supply Responses):</strong> Incorporates
            labor supply elasticities based on CBO estimates, with elasticities doubled for
            workers aged 65+ based on meta-analysis findings. This captures behavioral
            responses to changes in effective marginal tax rates.
          </p>
          <p>
            For most Social Security taxation reforms, the two approaches yield similar results
            (typically within 5%). The main exceptions are Roth-style swap options (Options 5
            and 6), which show larger differences due to behavioral effects of taxing employer
            payroll contributions.
          </p>
        </AccordionItem>
      </div>

      <div className="data-sources">
        <h3>External Resources</h3>
        <ul>
          <li>
            <a href="https://www.ssa.gov/oact/tr/2025/" target="_blank" rel="noopener noreferrer">
              2025 Social Security Trustees Report
            </a>
          </li>
          <li>
            <a
              href="https://policyengine.github.io/policyengine-us-data"
              target="_blank"
              rel="noopener noreferrer"
            >
              PolicyEngine US Data Documentation
            </a>
          </li>
          <li>
            <a
              href="https://github.com/PolicyEngine/crfb-tob-impacts"
              target="_blank"
              rel="noopener noreferrer"
            >
              Analysis Source Code (GitHub)
            </a>
          </li>
        </ul>
      </div>
    </section>
  )
}
