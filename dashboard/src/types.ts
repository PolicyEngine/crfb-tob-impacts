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
  // Calculated percentages - total
  pctOfOasdiPayroll: number
  pctOfGdp: number
  // Calculated percentages - by trust fund
  oasdiPctOfPayroll: number
  hiPctOfPayroll: number
  oasdiPctOfGdp: number
  hiPctOfGdp: number
}

export type DisplayUnit = 'dollars' | 'pctPayroll' | 'pctGdp'

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
    description: '85% taxation with permanent extension of the bonus senior deduction',
  },
  {
    id: 'option4',
    name: '85% Taxation, Replace Senior Deduction with $500 Credit',
    shortName: '85%, No Deduction, $500 Credit',
    description: '85% taxation and replace bonus senior deduction with $500 nonrefundable tax credit',
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
    description: 'Eliminate the bonus senior deduction',
  },
  {
    id: 'option8',
    name: 'Tax 100% of Benefits',
    shortName: '100% Taxation',
    description: '100% of all Social Security benefits taxable regardless of income',
  },
  {
    id: 'option9',
    name: 'Tax 90% of Benefits',
    shortName: '90% Taxation',
    description: '90% of all Social Security benefits taxable regardless of income',
  },
  {
    id: 'option10',
    name: 'Tax 95% of Benefits',
    shortName: '95% Taxation',
    description: '95% of all Social Security benefits taxable regardless of income',
  },
  {
    id: 'option11',
    name: '85% Taxation, Replace Senior Deduction with $700 Credit',
    shortName: '85%, No Deduction, $700 Credit',
    description: '85% taxation with $700 nonrefundable credit (phased out above $150k joint / $75k other), replacing senior deduction',
  },
  // Option 12 hidden temporarily - needs further review
  // {
  //   id: 'option12',
  //   name: 'Extended Roth-Style Swap',
  //   shortName: 'Extended Roth',
  //   description: 'Immediate employer payroll taxation with benefit taxation phased out 2029-2062',
  // },
  // Option 13 hidden temporarily - needs further review
  // {
  //   id: 'option13',
  //   name: 'Extended Roth-Style Swap vs Balanced Fix Baseline',
  //   shortName: 'Roth vs Balanced Fix',
  //   description: 'Option 12 scored against a baseline where trust fund gaps are closed via payroll tax increases starting 2035',
  // },
]

export interface ExternalEstimate {
  source: string
  scoringType: string
  tenYearImpact: number
  budgetWindow: string
  url: string
}

export const EXTERNAL_ESTIMATES: Record<string, ExternalEstimate[]> = {
  option1: [
    { source: 'CBO', scoringType: 'Conventional', tenYearImpact: -1600, budgetWindow: '2025-2034', url: 'https://www.cbo.gov/budget-options/56856' },
    { source: 'Social Security Trustees', scoringType: 'Conventional', tenYearImpact: -1800, budgetWindow: '2025-2034', url: 'https://www.ssa.gov/OACT/TR/2024/' },
    { source: 'Tax Foundation', scoringType: 'Conventional', tenYearImpact: -1400, budgetWindow: '2025-2034', url: 'https://taxfoundation.org/blog/trump-social-security-tax/' },
  ],
  option7: [
    { source: 'JCT', scoringType: 'Conventional', tenYearImpact: 66.3, budgetWindow: 'FY 2025-2034', url: 'https://www.jct.gov/publications/2025/jcx-26-25r/' },
  ],
}
