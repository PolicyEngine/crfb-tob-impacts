import { describe, it, expect } from 'vitest'
import { parse75YearData, calculateTotals } from '../utils/dataLoader'
import { REFORMS } from '../types'

describe('Data Loading', () => {
  it('should parse 75-year data with trust fund splits and economic context', () => {
    const csvData = `reform_name,year,baseline_revenue,reform_revenue,revenue_impact,baseline_tob_medicare_hi,reform_tob_medicare_hi,tob_medicare_hi_impact,baseline_tob_oasdi,reform_tob_oasdi,tob_oasdi_impact,baseline_tob_total,reform_tob_total,tob_total_impact,scoring_type,oasdi_net_impact,hi_net_impact
option1,2026,2577.12,2474.28,-102.84,82.28,0,-82.28,20.56,0,-20.56,102.84,0,-102.84,static,0,0`

    // Mock economic projections
    const economicProjections = new Map([
      [2026, { year: 2026, oasdiTaxablePayroll: 10000, hiTaxablePayroll: 12500, gdp: 25000 }]
    ])

    const result = parse75YearData(csvData, economicProjections)

    expect(result.option1).toBeDefined()
    expect(result.option1[0].tobMedicareHiImpact).toBe(-82.28)
    expect(result.option1[0].tobOasdiImpact).toBe(-20.56)
    expect(result.option1[0].oasdiTaxablePayroll).toBe(10000)
    expect(result.option1[0].hiTaxablePayroll).toBe(12500)
    expect(result.option1[0].gdp).toBe(25000)
    // pctOfOasdiPayroll = (-102.84 / 10000) * 100 = -1.0284
    expect(result.option1[0].pctOfOasdiPayroll).toBeCloseTo(-1.0284, 4)
  })

  it('should support current-law allocation for allocation-eligible options', () => {
    const csvData = `reform_name,year,baseline_revenue,reform_revenue,revenue_impact,baseline_tob_medicare_hi,reform_tob_medicare_hi,tob_medicare_hi_impact,baseline_tob_oasdi,reform_tob_oasdi,tob_oasdi_impact,baseline_tob_total,reform_tob_total,tob_total_impact,scoring_type,oasdi_net_impact,hi_net_impact
option1,2026,2577.12,2474.28,-100,40,0,-80,60,0,-20,100,0,-100,static,0,0`
    const economicProjections = new Map([
      [2026, { year: 2026, oasdiTaxablePayroll: 10000, hiTaxablePayroll: 12500, gdp: 25000 }]
    ])

    const baselineShares = parse75YearData(csvData, economicProjections, 'baselineShares')
    const currentLaw = parse75YearData(csvData, economicProjections, 'currentLaw')

    expect(baselineShares.option1[0].tobOasdiImpact).toBe(-60)
    expect(baselineShares.option1[0].tobMedicareHiImpact).toBe(-40)
    expect(currentLaw.option1[0].tobOasdiImpact).toBe(-20)
    expect(currentLaw.option1[0].tobMedicareHiImpact).toBe(-80)
  })

  it('should use direct branching impacts for option12', () => {
    const csvData = `reform_name,year,baseline_revenue,reform_revenue,revenue_impact,baseline_tob_medicare_hi,reform_tob_medicare_hi,tob_medicare_hi_impact,baseline_tob_oasdi,reform_tob_oasdi,tob_oasdi_impact,baseline_tob_total,reform_tob_total,tob_total_impact,scoring_type,oasdi_net_impact,hi_net_impact
option12,2026,2577.12,2474.28,-100,40,0,-40,60,0,-60,100,0,-100,static,-25,-75`
    const economicProjections = new Map([
      [2026, { year: 2026, oasdiTaxablePayroll: 10000, hiTaxablePayroll: 12500, gdp: 25000 }]
    ])

    const result = parse75YearData(csvData, economicProjections)

    expect(result.option12[0].revenueImpact).toBe(-100)
    expect(result.option12[0].tobOasdiImpact).toBe(-25)
    expect(result.option12[0].tobMedicareHiImpact).toBe(-75)
  })

  it('should calculate 10-year and 75-year totals with percentages', () => {
    const yearlyData = [
      { year: 2026, revenueImpact: -100, tobOasdiImpact: -20, tobMedicareHiImpact: -80, tobTotalImpact: -100, baselineRevenue: 1000, reformRevenue: 900, oasdiTaxablePayroll: 10000, hiTaxablePayroll: 12500, gdp: 25000, pctOfOasdiPayroll: -1, pctOfGdp: -0.4, oasdiPctOfPayroll: -0.2, hiPctOfPayroll: -0.64, oasdiPctOfGdp: -0.08, hiPctOfGdp: -0.32 },
      { year: 2027, revenueImpact: -110, tobOasdiImpact: -22, tobMedicareHiImpact: -88, tobTotalImpact: -110, baselineRevenue: 1100, reformRevenue: 990, oasdiTaxablePayroll: 10500, hiTaxablePayroll: 13000, gdp: 26000, pctOfOasdiPayroll: -1.05, pctOfGdp: -0.42, oasdiPctOfPayroll: -0.21, hiPctOfPayroll: -0.68, oasdiPctOfGdp: -0.08, hiPctOfGdp: -0.34 },
    ]

    const totals = calculateTotals(yearlyData)

    expect(totals.tenYear).toBe(-210)
    expect(totals.total).toBe(-210)
    // tenYearPctPayroll = -210 / (10000 + 10500) * 100 = -1.024%
    expect(totals.tenYearPctPayroll).toBeCloseTo(-1.024, 2)
    // tenYearPctGdp = -210 / (25000 + 26000) * 100 = -0.412%
    expect(totals.tenYearPctGdp).toBeCloseTo(-0.412, 2)
  })

  it('should expose the current reform list', () => {
    expect(REFORMS.length).toBe(13)
    expect(REFORMS.map(r => r.id)).toEqual([
      'option1', 'option2', 'option3', 'option4',
      'option5', 'option6', 'option7', 'option8',
      'option9', 'option10', 'option11', 'option12', 'option13'
    ])
  })
})
