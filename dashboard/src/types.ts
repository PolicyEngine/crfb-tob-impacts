export interface Reform {
  id: string
  name: string
  shortName: string
  description: string
}

export interface YearlyImpact {
  year: number
  revenueImpact: number
  tobOasdiImpact: number
  tobMedicareHiImpact: number
  tobTotalImpact: number
  baselineRevenue: number
  reformRevenue: number
  // Economic context from SSA Trustees Report
  oasdiTaxablePayroll: number
  gdp: number
  // Calculated percentages
  pctOfOasdiPayroll: number
  pctOfGdp: number
}

// SSA Trustees Report reference
export const SSA_TRUSTEES_REPORT = {
  url: 'https://www.ssa.gov/oact/tr/2025/lr6g6.html',
  title: '2025 Social Security Trustees Report - Table VI.G6',
  description: 'Operations of the OASI and DI Trust Funds, Calendar Years 2020-2100'
}

export interface ReformData {
  reform: Reform
  yearlyData: YearlyImpact[]
  tenYearTotal: number
  seventyFiveYearTotal: number
}

export const REFORMS: Reform[] = [
  {
    id: 'option1',
    name: 'Full Repeal of Social Security Benefit Taxation',
    shortName: 'Full Repeal',
    description: 'Complete elimination of Social Security benefit income taxation starting 2026',
  },
  {
    id: 'option2',
    name: 'Tax 85% of Benefits Uniformly',
    shortName: '85% Taxation',
    description: '85% of all Social Security benefits taxable regardless of income level',
  },
  {
    id: 'option3',
    name: 'Tax 85% with Bonus Senior Deduction',
    shortName: '85% + Senior Deduction',
    description: '85% taxation with permanent extension of the $6,000 bonus senior deduction',
  },
  {
    id: 'option4',
    name: 'Social Security Tax Credit System ($500)',
    shortName: '$500 Tax Credit',
    description: 'Replace bonus senior deduction with $500 nonrefundable tax credit',
  },
  {
    id: 'option5',
    name: 'Roth-Style Swap (Immediate)',
    shortName: 'Roth Swap',
    description: 'Tax employer payroll contributions instead of benefits starting 2026',
  },
  {
    id: 'option6',
    name: 'Phased Roth-Style Swap',
    shortName: 'Phased Roth',
    description: 'Gradual transition from taxing benefits to taxing employer contributions',
  },
  {
    id: 'option7',
    name: 'Eliminate Bonus Senior Deduction',
    shortName: 'No Senior Deduction',
    description: 'Eliminate the $6,000 bonus senior deduction from 2026-2028',
  },
  {
    id: 'option8',
    name: 'Tax 100% of Benefits',
    shortName: '100% Taxation',
    description: '100% of all Social Security benefits taxable regardless of income',
  },
]

export interface ExternalEstimate {
  source: string
  scoringType: string
  tenYearImpact: number
  budgetWindow: string
  citation: string
}

export const EXTERNAL_ESTIMATES: Record<string, ExternalEstimate[]> = {
  option1: [
    { source: 'CBO', scoringType: 'Conventional', tenYearImpact: -1600, budgetWindow: '2025-2034', citation: 'cbo2024options' },
    { source: 'Social Security Trustees', scoringType: 'Conventional', tenYearImpact: -1800, budgetWindow: '2025-2034', citation: 'ssa2024trustees' },
    { source: 'Tax Foundation', scoringType: 'Conventional', tenYearImpact: -1400, budgetWindow: '2025-2034', citation: 'taxfoundation2024trump' },
    { source: 'Tax Foundation', scoringType: 'Conventional', tenYearImpact: -1300, budgetWindow: '2025-2034', citation: 'taxfoundation2024trump' },
  ],
  option7: [
    { source: 'JCT', scoringType: 'Conventional', tenYearImpact: 66.3, budgetWindow: 'FY 2025-2034', citation: 'jct2025bonus' },
  ],
}
