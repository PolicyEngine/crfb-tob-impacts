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
          summary="Achieves <0.1% error on age distribution (86 categories), Social Security benefits, and taxable payroll using matrix-based calibration."
        >
          <p>
            <strong>GREG (Generalized Regression)</strong> calibration simultaneously matches
            three constraint types:
          </p>
          <ul>
            <li>
              <strong>Age Distribution</strong> — 86 categories: ages 0–84 individually, 85+
              aggregated. Source: SSA Single Year Age demographic projections.
            </li>
            <li>
              <strong>Social Security Benefits</strong> — Total OASDI benefit payments in
              nominal dollars, ensuring aggregate Social Security income matches SSA fiscal
              projections.
            </li>
            <li>
              <strong>Taxable Payroll</strong> — Total earnings subject to Social Security
              taxation, properly accounting for the annual wage base cap ($168,600 in 2024).
            </li>
          </ul>
          <div className="validation-callout">
            <p>
              <strong>Validation (2027):</strong> Social Security <code>$1,800B</code> ✓ |
              Taxable payroll <code>$11,627B</code> ✓ | Age 6 population{' '}
              <code>3,730,632</code> ✓ — all within 0.1% of SSA targets.
            </p>
          </div>
        </AccordionItem>

        <AccordionItem
          title="Data Sources"
          summary="Analysis uses Enhanced CPS 2024 and 2025 Social Security Trustees Report intermediate assumptions."
        >
          <p>
            <strong>Microdata:</strong> Enhanced CPS 2024 from PolicyEngine US, with tax record
            integration and machine learning imputation (quantile regression forests) for
            missing or underreported income.
          </p>
          <p>
            <strong>Demographic Projections:</strong> <code>SSPopJul_TR2024.csv</code> —
            Population by single year of age through 2100 from SSA Single Year Age Demographic
            Projections 2024.
          </p>
          <p>
            <strong>Fiscal Projections:</strong> <code>social_security_aux.csv</code> — OASDI
            costs and taxable payroll through 2100 from SSA 2025 Trustees Report Tables VI.G6
            and VI.G10.
          </p>
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
