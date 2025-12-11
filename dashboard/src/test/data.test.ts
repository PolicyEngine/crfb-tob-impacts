import { describe, it, expect } from 'vitest'
import { parseYearlyData, parse75YearData, calculateTotals } from '../utils/dataLoader'
import { REFORMS } from '../types'

describe('Data Loading', () => {
  it('should parse yearly CSV data correctly', () => {
    const csvData = `reform_name,year,revenue_impact,baseline_revenue,reform_revenue
option1,2026,-102.84,2577.12,2474.28
option1,2027,-111.00,2748.99,2637.99`

    const result = parseYearlyData(csvData)

    expect(result.option1).toBeDefined()
    expect(result.option1.length).toBe(2)
    expect(result.option1[0].year).toBe(2026)
    expect(result.option1[0].revenueImpact).toBe(-102.84)
  })

  it('should parse 75-year data with trust fund splits', () => {
    const csvData = `reform_name,year,baseline_revenue,reform_revenue,revenue_impact,baseline_tob_medicare_hi,reform_tob_medicare_hi,tob_medicare_hi_impact,baseline_tob_oasdi,reform_tob_oasdi,tob_oasdi_impact,baseline_tob_total,reform_tob_total,tob_total_impact,scoring_type
option1,2026,2577.12,2474.28,-102.84,82.28,0,-82.28,20.56,0,-20.56,102.84,0,-102.84,static`

    const result = parse75YearData(csvData)

    expect(result.option1).toBeDefined()
    expect(result.option1[0].tobMedicareHiImpact).toBe(-82.28)
    expect(result.option1[0].tobOasdiImpact).toBe(-20.56)
  })

  it('should calculate 10-year and 75-year totals', () => {
    const yearlyData = [
      { year: 2026, revenueImpact: -100, tobOasdiImpact: -20, tobMedicareHiImpact: -80, tobTotalImpact: -100, baselineRevenue: 1000, reformRevenue: 900 },
      { year: 2027, revenueImpact: -110, tobOasdiImpact: -22, tobMedicareHiImpact: -88, tobTotalImpact: -110, baselineRevenue: 1100, reformRevenue: 990 },
    ]

    const totals = calculateTotals(yearlyData)

    expect(totals.tenYear).toBe(-210)
    expect(totals.total).toBe(-210)
  })

  it('should have all 8 reform options defined', () => {
    expect(REFORMS.length).toBe(8)
    expect(REFORMS.map(r => r.id)).toEqual([
      'option1', 'option2', 'option3', 'option4',
      'option5', 'option6', 'option7', 'option8'
    ])
  })
})
