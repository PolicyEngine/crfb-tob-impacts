import type { YearlyImpact } from '../types'
import {
  splitRevenueImpacts,
  type AllocationInput,
  type AllocationMode,
} from './trustFundAllocation'
export { ALLOCATION_ELIGIBLE_OPTIONS } from './trustFundAllocation'
export type { AllocationMode } from './trustFundAllocation'

// SSA Trustees Report economic projections (Table VI.G6)
// Source: https://www.ssa.gov/oact/tr/2025/lr6g6.html
interface EconomicProjection {
  year: number
  oasdiTaxablePayroll: number  // billions
  hiTaxablePayroll: number  // billions
  gdp: number  // billions
}

// Get base URL from Vite's import.meta.env.BASE_URL
const BASE_URL = import.meta.env.BASE_URL || '/'

async function loadHiTaxablePayroll(): Promise<Map<number, number>> {
  const response = await fetch(`${BASE_URL}data/hi_taxable_payroll.csv`)
  if (!response.ok) {
    return new Map()
  }

  const csvContent = await response.text()
  const lines = csvContent.trim().split('\n')
  const hiPayroll = new Map<number, number>()

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    const year = parseInt(values[0])
    const amount = parseFloat(values[1])
    hiPayroll.set(year, amount)
  }

  return hiPayroll
}

async function loadEconomicProjections(): Promise<Map<number, EconomicProjection>> {
  const [response, hiTaxablePayroll] = await Promise.all([
    fetch(`${BASE_URL}data/ssa_economic_projections.csv`),
    loadHiTaxablePayroll(),
  ])
  const csvContent = await response.text()
  const lines = csvContent.trim().split('\n')
  const projections = new Map<number, EconomicProjection>()

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    const year = parseInt(values[0])
    const oasdiTaxablePayroll = parseFloat(values[1])
    const gdp = parseFloat(values[2])
    projections.set(year, {
      year,
      oasdiTaxablePayroll,
      hiTaxablePayroll: hiTaxablePayroll.get(year) ?? oasdiTaxablePayroll,
      gdp,
    })
  }

  return projections
}

export function parse75YearData(
  csvContent: string,
  economicProjections: Map<number, EconomicProjection>,
  allocationMode: AllocationMode = 'baselineShares'
): Record<string, YearlyImpact[]> {
  const lines = csvContent.trim().split('\n')
  const headers = lines[0].split(',')
  const headerIndex = new Map(headers.map((header, index) => [header, index]))
  const result: Record<string, YearlyImpact[]> = {}

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    const reformName = values[0]
    const year = parseInt(values[headerIndex.get('year') ?? -1])
    const baselineRevenue = parseFloat(values[headerIndex.get('baseline_revenue') ?? -1])
    const reformRevenue = parseFloat(values[headerIndex.get('reform_revenue') ?? -1])

    const allocationRow: AllocationInput = {
      reformName,
      revenueImpact: parseFloat(values[headerIndex.get('revenue_impact') ?? -1]) || 0,
      baselineTobOasdi: parseFloat(values[headerIndex.get('baseline_tob_oasdi') ?? -1]) || 0,
      baselineTobMedicareHi: parseFloat(values[headerIndex.get('baseline_tob_medicare_hi') ?? -1]) || 0,
      tobOasdiImpact: parseFloat(values[headerIndex.get('tob_oasdi_impact') ?? -1]) || 0,
      tobMedicareHiImpact: parseFloat(values[headerIndex.get('tob_medicare_hi_impact') ?? -1]) || 0,
      oasdiNetImpact: parseFloat(values[headerIndex.get('oasdi_net_impact') ?? -1]) || 0,
      hiNetImpact: parseFloat(values[headerIndex.get('hi_net_impact') ?? -1]) || 0,
    }
    const {
      revenueImpact,
      tobOasdiImpact,
      tobMedicareHiImpact,
      tobTotalImpact,
    } = splitRevenueImpacts(allocationRow, allocationMode)

    // Get economic context for this year
    const econ = economicProjections.get(year) || {
      oasdiTaxablePayroll: 0,
      hiTaxablePayroll: 0,
      gdp: 0,
    }

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
    const hiPctOfPayroll = econ.hiTaxablePayroll > 0
      ? (tobMedicareHiImpact / econ.hiTaxablePayroll) * 100
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
      hiTaxablePayroll: econ.hiTaxablePayroll,
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

// Cache fetched data to avoid re-downloading when only allocation mode changes
let cachedProjections: Map<number, EconomicProjection> | null = null
let cachedCsv: Record<string, string> = {}

export async function loadData(
  scoringType: ScoringType = 'static',
  allocationMode: AllocationMode = 'baselineShares'
): Promise<Record<string, YearlyImpact[]>> {
  if (!cachedProjections) {
    cachedProjections = await loadEconomicProjections()
  }

  const filename = scoringType === 'dynamic' ? 'all_dynamic_results.csv' : 'all_static_results.csv'
  if (!cachedCsv[filename]) {
    const response = await fetch(`${BASE_URL}data/${filename}`)
    cachedCsv[filename] = await response.text()
  }

  return parse75YearData(cachedCsv[filename], cachedProjections, allocationMode)
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
