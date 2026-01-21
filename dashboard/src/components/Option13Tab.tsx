import { useState, useEffect } from 'react'
import Plot from 'react-plotly.js'

interface Option13Data {
  year: number
  baselineSsBenefits: number
  baselineIncomesTax: number
  baselineSsGap: number
  baselineHiGap: number
  benefitMultiplier: number
  newEmployeeSsRate: number
  newEmployerSsRate: number
  newEmployeeHiRate: number
  newEmployerHiRate: number
  reformSsBenefits: number
  reformIncomeTax: number
  reformSsGap: number
  reformHiGap: number
  benefitCut: number
  incomeTaxImpact: number
  tobOasdiImpact: number
  tobHiImpact: number
  rateIncreaseSsRevenue: number
  rateIncreaseHiRevenue: number
  totalRateIncreaseRevenue: number
  ssRateIncreasePp: number
  hiRateIncreasePp: number
  tobOasdiLoss: number
  tobHiLoss: number
  ssGapAfter: number
  hiGapAfter: number
  totalGapAfter: number
}

// Current law rates (2024)
const CURRENT_SS_RATE = 0.062 // 6.2% each for employee/employer
const CURRENT_HI_RATE = 0.0145 // 1.45% each for employee/employer

const BASE_URL = import.meta.env.BASE_URL || '/'

async function loadOption13Data(): Promise<Option13Data[]> {
  const response = await fetch(`${BASE_URL}data/option13_balanced_fix.csv`)
  const csvContent = await response.text()
  const lines = csvContent.trim().split('\n')
  const data: Option13Data[] = []

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    data.push({
      year: parseInt(values[0]),
      baselineSsBenefits: parseFloat(values[1]),
      baselineIncomesTax: parseFloat(values[2]),
      baselineSsGap: parseFloat(values[3]),
      baselineHiGap: parseFloat(values[4]),
      benefitMultiplier: parseFloat(values[5]),
      newEmployeeSsRate: parseFloat(values[6]),
      newEmployerSsRate: parseFloat(values[7]),
      newEmployeeHiRate: parseFloat(values[8]),
      newEmployerHiRate: parseFloat(values[9]),
      reformSsBenefits: parseFloat(values[10]),
      reformIncomeTax: parseFloat(values[11]),
      reformSsGap: parseFloat(values[12]),
      reformHiGap: parseFloat(values[13]),
      benefitCut: parseFloat(values[14]),
      incomeTaxImpact: parseFloat(values[15]),
      tobOasdiImpact: parseFloat(values[16]),
      tobHiImpact: parseFloat(values[17]),
      rateIncreaseSsRevenue: parseFloat(values[18]),
      rateIncreaseHiRevenue: parseFloat(values[19]),
      totalRateIncreaseRevenue: parseFloat(values[20]),
      ssRateIncreasePp: parseFloat(values[21]),
      hiRateIncreasePp: parseFloat(values[22]),
      tobOasdiLoss: parseFloat(values[23]),
      tobHiLoss: parseFloat(values[24]),
      ssGapAfter: parseFloat(values[25]),
      hiGapAfter: parseFloat(values[26]),
      totalGapAfter: parseFloat(values[27]),
    })
  }

  return data.sort((a, b) => a.year - b.year)
}

export function Option13Tab() {
  const [data, setData] = useState<Option13Data[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadOption13Data()
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="loading">Loading Option 13 data...</div>
  }

  if (data.length === 0) {
    return <div className="error">No Option 13 data available</div>
  }

  // Calculate metrics for display
  const years = data.map(d => d.year)
  const benefitCutPct = data.map(d => (1 - d.benefitMultiplier) * 100)
  const ssRateIncrease = data.map(d => (d.newEmployeeSsRate - CURRENT_SS_RATE) * 100 * 2) // Combined employee+employer
  const hiRateIncrease = data.map(d => (d.newEmployeeHiRate - CURRENT_HI_RATE) * 100 * 2)
  const ssGapBefore = data.map(d => d.baselineSsGap / 1e9)
  const ssGapAfterArr = data.map(d => d.ssGapAfter / 1e9)
  const hiGapBefore = data.map(d => d.baselineHiGap / 1e9)
  const hiGapAfterArr = data.map(d => d.hiGapAfter / 1e9)
  // Combined gap (SS + HI)
  const combinedGapBefore = data.map(d => (d.baselineSsGap + d.baselineHiGap) / 1e9)
  const combinedGapAfter = data.map(d => d.totalGapAfter / 1e9)

  return (
    <div className="option13-tab">
      <div className="option13-intro">
        <h2>Option 13: Balanced Fix Baseline</h2>
        <p className="option13-description">
          This baseline scenario closes trust fund gaps starting in 2035 using the "traditional fix" approach:
          SS Gap is closed with 50% benefit cuts and 50% payroll tax increases;
          HI Gap is closed with 100% payroll tax increases (no Medicare benefit cuts).
          Unlike Options 1-12, this does NOT include the employer payroll tax reform — providing an apples-to-apples comparison with current law.
        </p>
      </div>

      <div className="option13-summary-cards">
        <div className="summary-card">
          <div className="card-label">Benefit Cut (2035)</div>
          <div className="card-value negative">{benefitCutPct[0]?.toFixed(1)}%</div>
        </div>
        <div className="summary-card">
          <div className="card-label">SS Tax Increase (2035)</div>
          <div className="card-value positive">+{ssRateIncrease[0]?.toFixed(2)}pp</div>
        </div>
        <div className="summary-card">
          <div className="card-label">HI Tax Increase (2035)</div>
          <div className="card-value positive">+{hiRateIncrease[0]?.toFixed(2)}pp</div>
        </div>
        <div className="summary-card">
          <div className="card-label">Combined Gap (2035)</div>
          <div className="card-value">${Math.abs(combinedGapBefore[0])?.toFixed(0)}B → ${combinedGapAfter[0]?.toFixed(0)}B</div>
        </div>
      </div>

      <div className="option13-charts">
        <div className="chart-container">
          <Plot
            data={[
              {
                x: years,
                y: benefitCutPct,
                type: 'bar',
                name: 'Benefit Cut',
                marker: { color: '#e74c3c' },
                hovertemplate: 'Year %{x}<br>Benefit Cut: %{y:.1f}%<extra></extra>',
              },
            ]}
            layout={{
              title: 'Benefit Cuts by Year',
              xaxis: { title: 'Year', tickmode: 'array', tickvals: years },
              yaxis: { title: 'Benefit Cut (%)', ticksuffix: '%' },
              margin: { t: 50, b: 50, l: 60, r: 30 },
              height: 300,
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>

        <div className="chart-container">
          <Plot
            data={[
              {
                x: years,
                y: ssRateIncrease,
                type: 'bar',
                name: 'SS Rate',
                marker: { color: '#3498db' },
                hovertemplate: 'Year %{x}<br>SS Increase: +%{y:.2f}pp<extra></extra>',
              },
              {
                x: years,
                y: hiRateIncrease,
                type: 'bar',
                name: 'HI Rate',
                marker: { color: '#9b59b6' },
                hovertemplate: 'Year %{x}<br>HI Increase: +%{y:.2f}pp<extra></extra>',
              },
            ]}
            layout={{
              title: 'Payroll Tax Rate Increases',
              xaxis: { title: 'Year', tickmode: 'array', tickvals: years },
              yaxis: { title: 'Rate Increase (pp)', ticksuffix: 'pp' },
              margin: { t: 50, b: 50, l: 60, r: 30 },
              height: 300,
              barmode: 'group',
              legend: { orientation: 'h', y: -0.2 },
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>

        <div className="chart-container">
          <Plot
            data={[
              {
                x: years,
                y: ssGapBefore,
                type: 'bar',
                name: 'Before (Current Law)',
                marker: { color: '#e74c3c' },
                hovertemplate: 'Year %{x}<br>SS Gap: $%{y:.0f}B<extra></extra>',
              },
              {
                x: years,
                y: ssGapAfterArr,
                type: 'bar',
                name: 'After (Balanced Fix)',
                marker: { color: '#27ae60' },
                hovertemplate: 'Year %{x}<br>SS Gap: $%{y:.0f}B<extra></extra>',
              },
            ]}
            layout={{
              title: 'Social Security Trust Fund Gap',
              xaxis: { title: 'Year', tickmode: 'array', tickvals: years },
              yaxis: { title: 'Gap ($B)', tickprefix: '$', ticksuffix: 'B' },
              margin: { t: 50, b: 50, l: 70, r: 30 },
              height: 300,
              barmode: 'group',
              legend: { orientation: 'h', y: -0.2 },
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>

        <div className="chart-container">
          <Plot
            data={[
              {
                x: years,
                y: hiGapBefore,
                type: 'bar',
                name: 'Before (Current Law)',
                marker: { color: '#e74c3c' },
                hovertemplate: 'Year %{x}<br>HI Gap: $%{y:.0f}B<extra></extra>',
              },
              {
                x: years,
                y: hiGapAfterArr,
                type: 'bar',
                name: 'After (Balanced Fix)',
                marker: { color: '#27ae60' },
                hovertemplate: 'Year %{x}<br>HI Gap: $%{y:.0f}B<extra></extra>',
              },
            ]}
            layout={{
              title: 'Medicare HI Trust Fund Gap',
              xaxis: { title: 'Year', tickmode: 'array', tickvals: years },
              yaxis: { title: 'Gap ($B)', tickprefix: '$', ticksuffix: 'B' },
              margin: { t: 50, b: 50, l: 70, r: 30 },
              height: 300,
              barmode: 'group',
              legend: { orientation: 'h', y: -0.2 },
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>

        <div className="chart-container">
          <Plot
            data={[
              {
                x: years,
                y: combinedGapBefore,
                type: 'bar',
                name: 'Before (Current Law)',
                marker: { color: '#e74c3c' },
                hovertemplate: 'Year %{x}<br>Combined Gap: $%{y:.0f}B<extra></extra>',
              },
              {
                x: years,
                y: combinedGapAfter,
                type: 'bar',
                name: 'After (Balanced Fix)',
                marker: { color: '#27ae60' },
                hovertemplate: 'Year %{x}<br>Combined Gap: $%{y:.0f}B<extra></extra>',
              },
            ]}
            layout={{
              title: 'Combined Trust Fund Gap (SS + HI)',
              xaxis: { title: 'Year', tickmode: 'array', tickvals: years },
              yaxis: { title: 'Gap ($B)', tickprefix: '$', ticksuffix: 'B' },
              margin: { t: 50, b: 50, l: 70, r: 30 },
              height: 300,
              barmode: 'group',
              legend: { orientation: 'h', y: -0.2 },
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>
      </div>

      <div className="option13-table">
        <h3>Detailed Results by Year</h3>
        <table>
          <thead>
            <tr>
              <th>Year</th>
              <th>Benefit Cut</th>
              <th>SS Rate</th>
              <th>HI Rate</th>
              <th>SS Gap (Before)</th>
              <th>SS Gap (After)</th>
              <th>HI Gap (Before)</th>
              <th>HI Gap (After)</th>
              <th>Combined (Before)</th>
              <th>Combined (After)</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={row.year}>
                <td>{row.year}</td>
                <td className="negative">{benefitCutPct[i].toFixed(1)}%</td>
                <td>{(row.newEmployeeSsRate * 2 * 100).toFixed(2)}%</td>
                <td>{(row.newEmployeeHiRate * 2 * 100).toFixed(2)}%</td>
                <td className="negative">${ssGapBefore[i].toFixed(0)}B</td>
                <td className="positive">${ssGapAfterArr[i].toFixed(0)}B</td>
                <td className="negative">${hiGapBefore[i].toFixed(0)}B</td>
                <td className="positive">${hiGapAfterArr[i].toFixed(0)}B</td>
                <td className="negative">${combinedGapBefore[i].toFixed(0)}B</td>
                <td className="positive">${combinedGapAfter[i].toFixed(0)}B</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="option13-methodology">
        <h3>Methodology: Step-by-Step Gap Closing</h3>
        <p className="methodology-intro">
          Option 13 is the "traditional fix" baseline — it closes trust fund gaps using only benefit cuts and payroll tax rate increases.
          This provides an apples-to-apples comparison with current law (no employer payroll tax reform).
        </p>

        <h4>Step 1: Calculate Baseline Gaps</h4>
        <p>Run PolicyEngine microsimulation under current law to measure trust fund gaps:</p>
        <ul>
          <li><strong>SS Income</strong> = employee_ss_tax + employer_ss_tax + tob_oasdi</li>
          <li><strong>SS Outgo</strong> = social_security benefits</li>
          <li><strong>SS Gap</strong> = SS Income − SS Outgo (negative = deficit)</li>
        </ul>
        <ul>
          <li><strong>HI Income</strong> = employee_hi_tax + employer_hi_tax + additional_medicare_tax + tob_hi</li>
          <li><strong>HI Outgo</strong> = Medicare expenditures (from 2025 Trustees Report)</li>
          <li><strong>HI Gap</strong> = HI Income − HI Outgo (negative = deficit)</li>
        </ul>
        <p><em>Note: Medicare expenditures come from Trustees data because PolicyEngine models tax revenue but not Medicare spending.</em></p>

        <h4>Step 2: Apply 50% Benefit Cuts (Stage 1)</h4>
        <p>Calculate SS benefit reduction:</p>
        <ul>
          <li><strong>benefit_cut</strong> = |SS Gap| × 0.5 (50% of the shortfall)</li>
          <li><strong>benefit_multiplier</strong> = 1 − (benefit_cut ÷ total_ss_benefits)</li>
        </ul>
        <p>Run simulation with reduced SS benefits using <code>set_input("social_security", year, benefits × multiplier)</code></p>
        <p>This automatically captures TOB feedback — lower benefits mean less taxable SS income, reducing tob_oasdi and tob_hi.</p>

        <h4>Step 3: Measure Remaining Gaps</h4>
        <p>After benefit cuts, calculate remaining gaps from Stage 1 simulation:</p>
        <ul>
          <li><strong>remaining_ss_gap</strong> = stage1_ss_income − stage1_ss_benefits</li>
          <li><strong>remaining_hi_gap</strong> = stage1_hi_income − medicare_expenditures</li>
        </ul>
        <p>These gaps reflect the TOB losses naturally — no separate estimation needed.</p>

        <h4>Step 4: Calculate Rate Increases (Stage 2)</h4>
        <p>Determine payroll tax rate increases to close remaining gaps:</p>
        <ul>
          <li><strong>ss_rate_increase</strong> = |remaining_ss_gap| ÷ oasdi_taxable_payroll</li>
          <li><strong>hi_rate_increase</strong> = |remaining_hi_gap| ÷ hi_taxable_payroll</li>
        </ul>
        <p>Taxable payroll is measured directly from PolicyEngine:</p>
        <ul>
          <li><strong>oasdi_taxable_payroll</strong> = sum of <code>taxable_earnings_for_social_security</code> (capped at wage base)</li>
          <li><strong>hi_taxable_payroll</strong> = sum of <code>payroll_tax_gross_wages</code> (no cap)</li>
        </ul>

        <h4>Step 5: Apply Rate Increases and Verify</h4>
        <p>Split rate increases 50/50 between employee and employer:</p>
        <ul>
          <li><strong>new_employee_rate</strong> = current_rate + (rate_increase ÷ 2)</li>
          <li><strong>new_employer_rate</strong> = current_rate + (rate_increase ÷ 2)</li>
        </ul>
        <p>Run final simulation with rate increases + benefit cuts applied. Verify final gaps are ≈ $0.</p>

        <h4>Key Design Decisions</h4>
        <ul>
          <li><strong>No employer payroll tax reform:</strong> Unlike Options 1-12, Option 13 does NOT tax employer contributions as income. This keeps the comparison clean.</li>
          <li><strong>SS: 50% cuts + 50% rate increases:</strong> Balances burden between beneficiaries and workers.</li>
          <li><strong>HI: 100% rate increases:</strong> No Medicare benefit cuts (Medicare Part A doesn't have the same direct benefit structure as SS).</li>
          <li><strong>Two-stage approach:</strong> Measure actual gaps after benefit cuts instead of estimating TOB losses upfront.</li>
        </ul>
      </div>
    </div>
  )
}
