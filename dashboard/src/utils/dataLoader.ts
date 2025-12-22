import type { YearlyImpact } from '../types'

// SSA Trustees Report economic projections (Table VI.G6)
// Source: https://www.ssa.gov/oact/tr/2025/lr6g6.html
interface EconomicProjection {
  year: number
  oasdiTaxablePayroll: number  // billions
  gdp: number  // billions
}

// Get base URL from Vite's import.meta.env.BASE_URL
const BASE_URL = import.meta.env.BASE_URL || '/'

async function loadEconomicProjections(): Promise<Map<number, EconomicProjection>> {
  const response = await fetch(`${BASE_URL}data/ssa_economic_projections.csv`)
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
    const baselineRevenue = parseFloat(values[headers.indexOf('baseline_revenue')])
    const reformRevenue = parseFloat(values[headers.indexOf('reform_revenue')])

    // Different options use different columns for impacts
    const isOption4 = reformName === 'option4'
    const isOption5or6 = reformName === 'option5' || reformName === 'option6'
    const isOption7 = reformName === 'option7'

    let tobOasdiImpact: number
    let tobMedicareHiImpact: number
    let revenueImpact: number

    if (isOption7) {
      // Option 7: Revenue goes to general revenues, not trust funds
      // Use revenue_impact directly, set trust fund splits to 0
      revenueImpact = parseFloat(values[headers.indexOf('revenue_impact')]) || 0
      tobOasdiImpact = 0
      tobMedicareHiImpact = 0
    } else if (isOption4) {
      // Option 4: Allocate full revenue_impact to trust funds based on baseline shares
      // "The additional revenue raised will be allocated to the OASDI and HI trust funds
      // in a way that maintains the current projected shares of contributions from TOB revenue"
      revenueImpact = parseFloat(values[headers.indexOf('revenue_impact')]) || 0
      const baselineOasdi = parseFloat(values[headers.indexOf('baseline_tob_oasdi')]) || 0
      const baselineHi = parseFloat(values[headers.indexOf('baseline_tob_medicare_hi')]) || 0
      const baselineTotal = baselineOasdi + baselineHi

      if (baselineTotal > 0) {
        const oasdiShare = baselineOasdi / baselineTotal
        const hiShare = baselineHi / baselineTotal
        tobOasdiImpact = revenueImpact * oasdiShare
        tobMedicareHiImpact = revenueImpact * hiShare
      } else {
        tobOasdiImpact = 0
        tobMedicareHiImpact = 0
      }
    } else if (isOption5or6) {
      // Options 5-6: use oasdi_net_impact and hi_net_impact
      tobOasdiImpact = parseFloat(values[headers.indexOf('oasdi_net_impact')]) || 0
      tobMedicareHiImpact = parseFloat(values[headers.indexOf('hi_net_impact')]) || 0
      revenueImpact = tobOasdiImpact + tobMedicareHiImpact
    } else {
      // Options 1-3, 8: use tob_oasdi_impact and tob_medicare_hi_impact
      tobOasdiImpact = parseFloat(values[headers.indexOf('tob_oasdi_impact')]) || 0
      tobMedicareHiImpact = parseFloat(values[headers.indexOf('tob_medicare_hi_impact')]) || 0
      revenueImpact = tobOasdiImpact + tobMedicareHiImpact
    }

    // Total trust fund impact
    const tobTotalImpact = tobOasdiImpact + tobMedicareHiImpact

    // Get economic context for this year
    const econ = economicProjections.get(year) || { oasdiTaxablePayroll: 0, gdp: 0 }

    // Calculate percentages (revenue impact is in billions, so is payroll/GDP)
    const pctOfOasdiPayroll = econ.oasdiTaxablePayroll > 0
      ? (revenueImpact / econ.oasdiTaxablePayroll) * 100
      : 0
    const pctOfGdp = econ.gdp > 0
      ? (revenueImpact / econ.gdp) * 100
      : 0

    // Calculate percentages by trust fund
    const oasdiPctOfPayroll = econ.oasdiTaxablePayroll > 0
      ? (tobOasdiImpact / econ.oasdiTaxablePayroll) * 100
      : 0
    const hiPctOfPayroll = econ.oasdiTaxablePayroll > 0
      ? (tobMedicareHiImpact / econ.oasdiTaxablePayroll) * 100
      : 0
    const oasdiPctOfGdp = econ.gdp > 0
      ? (tobOasdiImpact / econ.gdp) * 100
      : 0
    const hiPctOfGdp = econ.gdp > 0
      ? (tobMedicareHiImpact / econ.gdp) * 100
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
      oasdiPctOfPayroll,
      hiPctOfPayroll,
      oasdiPctOfGdp,
      hiPctOfGdp,
    })
  }

  // Sort each reform's data by year
  for (const reformName in result) {
    result[reformName].sort((a, b) => a.year - b.year)
  }

  return result
}

export function calculateTotals(data: YearlyImpact[]): {
  tenYear: number
  total: number
  tenYearPctPayroll: number
  tenYearPctGdp: number
  totalPctPayroll: number
  totalPctGdp: number
} {
  const tenYearData = data.filter(d => d.year >= 2026 && d.year <= 2035)
  const tenYear = tenYearData.reduce((sum, d) => sum + d.revenueImpact, 0)
  const total = data.reduce((sum, d) => sum + d.revenueImpact, 0)

  // Calculate 10-year totals for payroll and GDP
  const tenYearPayroll = tenYearData.reduce((sum, d) => sum + d.oasdiTaxablePayroll, 0)
  const tenYearGdp = tenYearData.reduce((sum, d) => sum + d.gdp, 0)

  const tenYearPctPayroll = tenYearPayroll > 0 ? (tenYear / tenYearPayroll) * 100 : 0
  const tenYearPctGdp = tenYearGdp > 0 ? (tenYear / tenYearGdp) * 100 : 0

  // Calculate 75-year totals for payroll and GDP
  const totalPayroll = data.reduce((sum, d) => sum + d.oasdiTaxablePayroll, 0)
  const totalGdp = data.reduce((sum, d) => sum + d.gdp, 0)

  const totalPctPayroll = totalPayroll > 0 ? (total / totalPayroll) * 100 : 0
  const totalPctGdp = totalGdp > 0 ? (total / totalGdp) * 100 : 0

  return { tenYear, total, tenYearPctPayroll, tenYearPctGdp, totalPctPayroll, totalPctGdp }
}

export type ScoringType = 'static' | 'dynamic'
export type { DisplayUnit } from '../types'

export async function loadData(scoringType: ScoringType = 'static'): Promise<Record<string, YearlyImpact[]>> {
  // Load economic projections first
  const economicProjections = await loadEconomicProjections()

  // Load and parse the results data based on scoring type
  const filename = scoringType === 'dynamic' ? 'all_dynamic_results.csv' : 'all_static_results.csv'
  const response = await fetch(`${BASE_URL}data/${filename}`)
  const csvContent = await response.text()
  return parse75YearData(csvContent, economicProjections)
}

export function exportToCsv(data: YearlyImpact[], reformId: string, reformName: string): void {
  // CSV header
  const headers = [
    'Reform',
    'Year',
    'Revenue Impact ($B)',
    'OASDI Impact ($B)',
    'Medicare HI Impact ($B)',
    'Total TOB Impact ($B)',
    'Baseline Revenue ($B)',
    'Reform Revenue ($B)',
    '% of OASDI Payroll',
    '% of GDP'
  ]

  // CSV rows
  const rows = data.map(d => [
    reformName,
    d.year,
    d.revenueImpact.toFixed(2),
    d.tobOasdiImpact.toFixed(2),
    d.tobMedicareHiImpact.toFixed(2),
    d.tobTotalImpact.toFixed(2),
    d.baselineRevenue.toFixed(2),
    d.reformRevenue.toFixed(2),
    d.pctOfOasdiPayroll.toFixed(3),
    d.pctOfGdp.toFixed(3)
  ])

  // Combine header and rows
  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n')

  // Create and trigger download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', `${reformId}_impact_data.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
