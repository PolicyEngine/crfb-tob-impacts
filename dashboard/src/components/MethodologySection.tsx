export function MethodologySection() {
  return (
    <section className="methodology-section">
      <h2>Methodology</h2>

      <div className="methodology-content">
        <div className="method-card">
          <h3>Microsimulation Model</h3>
          <p>
            This analysis uses the <strong>PolicyEngine US</strong> microsimulation model with the
            <strong> Enhanced CPS (2024)</strong> dataset. The model applies tax-unit level calculations
            to estimate revenue impacts from policy changes.
          </p>
        </div>

        <div className="method-card">
          <h3>Long-Term Projections</h3>
          <p>
            75-year projections (2026-2100) use demographic and economic targets from the
            <strong> 2025 Social Security Trustees Report</strong>. Dataset weights are calibrated
            to match SSA age distributions, benefit totals, and taxable payroll projections.
          </p>
        </div>

        <div className="method-card">
          <h3>Trust Fund Allocation</h3>
          <p>
            Revenue allocation varies by option: <strong>Options 1-3 & 8</strong> use current law rules
            (50% of taxable benefits to OASDI, additional 35% to HI). <strong>Option 4</strong> allocates
            revenue to maintain current projected trust fund shares. <strong>Options 5-6</strong> direct
            employer contribution taxes to their respective trust funds. <strong>Option 7</strong> revenue
            is allocated to general revenues, not trust funds.
          </p>
        </div>

        <div className="method-card">
          <h3>Scoring Approach</h3>
          <p>
            Estimates shown use <strong>static scoring</strong>, which holds taxpayer behavior constant.
            Labor supply response estimates (incorporating CBO elasticities, doubled for 65+) are
            typically within 5% of static estimates for most options.
          </p>
        </div>
      </div>

      <div className="data-sources">
        <h3>Data Sources</h3>
        <ul>
          <li>
            <a href="https://www.ssa.gov/oact/tr/2025/" target="_blank" rel="noopener noreferrer">
              2025 Social Security Trustees Report
            </a>
          </li>
          <li>
            <a href="https://policyengine.github.io/policyengine-us-data" target="_blank" rel="noopener noreferrer">
              PolicyEngine US Data Documentation
            </a>
          </li>
          <li>
            <a href="https://github.com/PolicyEngine/crfb-tob-impacts" target="_blank" rel="noopener noreferrer">
              Analysis Source Code (GitHub)
            </a>
          </li>
        </ul>
      </div>
    </section>
  )
}
