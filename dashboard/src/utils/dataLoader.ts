import type { YearlyImpact } from '../types'

// SSA Trustees Report economic projections (Table VI.G6)
// Source: https://www.ssa.gov/oact/tr/2025/lr6g6.html
interface EconomicProjection {
  year: number
  oasdiTaxablePayroll: number  // billions
  gdp: number  // billions
}

async function loadEconomicProjections(): Promise<Map<number, EconomicProjection>> {
  const response = await fetch('/data/ssa_economic_projections.csv')
  const csvContent = await response.text()
  const lines = csvContent.trim().split('\n')
  const projections = new Map<number, EconomicProjection>()

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    const year = parseInt(values[0])
    const oasdiTaxablePayroll = parseFloat(values[1])
    const gdp = parseFloat(values[2])
    projections.set(year, { year, oasdiTaxablePayroll, gdp })
  }

  return projections
}

export function parse75YearData(
  csvContent: string,
  economicProjections: Map<number, EconomicProjection>
): Record<string, YearlyImpact[]> {
  const lines = csvContent.trim().split('\n')
  const headers = lines[0].split(',')
  const result: Record<string, YearlyImpact[]> = {}

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    const reformName = values[0]
    const year = parseInt(values[headers.indexOf('year')])
    const revenueImpact = parseFloat(values[headers.indexOf('revenue_impact')])
    const baselineRevenue = parseFloat(values[headers.indexOf('baseline_revenue')])
    const reformRevenue = parseFloat(values[headers.indexOf('reform_revenue')])
    const tobMedicareHiImpact = parseFloat(values[headers.indexOf('tob_medicare_hi_impact')])
    const tobOasdiImpact = parseFloat(values[headers.indexOf('tob_oasdi_impact')])
    const tobTotalImpact = parseFloat(values[headers.indexOf('tob_total_impact')])

    // Get economic context for this year
    const econ = economicProjections.get(year) || { oasdiTaxablePayroll: 0, gdp: 0 }

    // Calculate percentages (revenue impact is in billions, so is payroll/GDP)
    const pctOfOasdiPayroll = econ.oasdiTaxablePayroll > 0
      ? (revenueImpact / econ.oasdiTaxablePayroll) * 100
      : 0
    const pctOfGdp = econ.gdp > 0
      ? (revenueImpact / econ.gdp) * 100
      : 0

    if (!result[reformName]) {
      result[reformName] = []
    }

    result[reformName].push({
      year,
      revenueImpact,
      baselineRevenue,
      reformRevenue,
      tobOasdiImpact,
      tobMedicareHiImpact,
      tobTotalImpact,
      oasdiTaxablePayroll: econ.oasdiTaxablePayroll,
      gdp: econ.gdp,
      pctOfOasdiPayroll,
      pctOfGdp,
    })
  }

  return result
}

export function calculateTotals(data: YearlyImpact[]): {
  tenYear: number
  total: number
  tenYearPctPayroll: number
  tenYearPctGdp: number
} {
  const tenYearData = data.filter(d => d.year >= 2026 && d.year <= 2035)
  const tenYear = tenYearData.reduce((sum, d) => sum + d.revenueImpact, 0)
  const total = data.reduce((sum, d) => sum + d.revenueImpact, 0)

  // Calculate 10-year totals for payroll and GDP
  const tenYearPayroll = tenYearData.reduce((sum, d) => sum + d.oasdiTaxablePayroll, 0)
  const tenYearGdp = tenYearData.reduce((sum, d) => sum + d.gdp, 0)

  const tenYearPctPayroll = tenYearPayroll > 0 ? (tenYear / tenYearPayroll) * 100 : 0
  const tenYearPctGdp = tenYearGdp > 0 ? (tenYear / tenYearGdp) * 100 : 0

  return { tenYear, total, tenYearPctPayroll, tenYearPctGdp }
}

export async function loadData(): Promise<Record<string, YearlyImpact[]>> {
  // Load economic projections first
  const economicProjections = await loadEconomicProjections()

  // Load and parse the 75-year data with economic context
  const response = await fetch('/data/75_year_tf_splits.csv')
  const csvContent = await response.text()
  return parse75YearData(csvContent, economicProjections)
}
