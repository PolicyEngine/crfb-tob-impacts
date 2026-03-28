import allocationRulesJson from '../config/trustFundAllocationRules.json'

export type AllocationMode = 'currentLaw' | 'baselineShares'

interface AllocationRules {
  allocationEligibleOptions: string[]
  baselineShareOptions: string[]
  netImpactOptions: string[]
  directBranchingOptions: string[]
  generalRevenueOptions: string[]
}

export interface AllocationInput {
  reformName: string
  revenueImpact: number
  baselineTobOasdi: number
  baselineTobMedicareHi: number
  tobOasdiImpact: number
  tobMedicareHiImpact: number
  oasdiNetImpact: number
  hiNetImpact: number
}

export interface AllocationResult {
  revenueImpact: number
  tobOasdiImpact: number
  tobMedicareHiImpact: number
  tobTotalImpact: number
}

const allocationRules = allocationRulesJson as AllocationRules

const allocationEligibleOptions = new Set(allocationRules.allocationEligibleOptions)
const baselineShareOptions = new Set(allocationRules.baselineShareOptions)
const netImpactOptions = new Set(allocationRules.netImpactOptions)
const directBranchingOptions = new Set(allocationRules.directBranchingOptions)
const generalRevenueOptions = new Set(allocationRules.generalRevenueOptions)

export const ALLOCATION_ELIGIBLE_OPTIONS = allocationRules.allocationEligibleOptions

export function splitRevenueImpacts(
  row: AllocationInput,
  allocationMode: AllocationMode = 'baselineShares'
): AllocationResult {
  if (generalRevenueOptions.has(row.reformName)) {
    return {
      revenueImpact: row.revenueImpact,
      tobOasdiImpact: 0,
      tobMedicareHiImpact: 0,
      tobTotalImpact: 0,
    }
  }

  if (directBranchingOptions.has(row.reformName)) {
    const revenueImpact = row.oasdiNetImpact + row.hiNetImpact
    return {
      revenueImpact,
      tobOasdiImpact: row.oasdiNetImpact,
      tobMedicareHiImpact: row.hiNetImpact,
      tobTotalImpact: revenueImpact,
    }
  }

  const usesBaselineShares = baselineShareOptions.has(row.reformName)
    || (allocationMode === 'baselineShares' && allocationEligibleOptions.has(row.reformName))
  if (usesBaselineShares) {
    const baselineTotal = row.baselineTobOasdi + row.baselineTobMedicareHi
    if (baselineTotal <= 0) {
      return {
        revenueImpact: row.revenueImpact,
        tobOasdiImpact: 0,
        tobMedicareHiImpact: 0,
        tobTotalImpact: 0,
      }
    }

    const tobOasdiImpact = row.revenueImpact * (row.baselineTobOasdi / baselineTotal)
    const tobMedicareHiImpact = row.revenueImpact - tobOasdiImpact
    return {
      revenueImpact: row.revenueImpact,
      tobOasdiImpact,
      tobMedicareHiImpact,
      tobTotalImpact: row.revenueImpact,
    }
  }

  if (netImpactOptions.has(row.reformName)) {
    const revenueImpact = row.oasdiNetImpact + row.hiNetImpact
    return {
      revenueImpact,
      tobOasdiImpact: row.oasdiNetImpact,
      tobMedicareHiImpact: row.hiNetImpact,
      tobTotalImpact: revenueImpact,
    }
  }

  const revenueImpact = row.tobOasdiImpact + row.tobMedicareHiImpact
  return {
    revenueImpact,
    tobOasdiImpact: row.tobOasdiImpact,
    tobMedicareHiImpact: row.tobMedicareHiImpact,
    tobTotalImpact: revenueImpact,
  }
}
