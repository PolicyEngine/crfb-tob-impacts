import Papa from "papaparse";

export type ScoringType = "static";
export type AllocationMode = "currentLaw" | "baselineShares";
export type DisplayUnit = "dollars" | "pctPayroll" | "pctGdp";

export interface YearlyImpact {
  year: number;
  revenueImpact: number;
  tobOasdiImpact: number;
  tobMedicareHiImpact: number;
  tobTotalImpact: number;
  baselineRevenue: number;
  reformRevenue: number;
  baselineTobOasdi: number;
  baselineTobMedicareHi: number;
  baselineTobTotal: number;
  oasdiTaxablePayroll: number;
  hiTaxablePayroll: number;
  gdp: number;
  pctOfOasdiPayroll: number;
  pctOfGdp: number;
  oasdiPctOfPayroll: number;
  hiPctOfPayroll: number;
  oasdiPctOfGdp: number;
  hiPctOfGdp: number;
}

interface EconomicProjection {
  year: number;
  oasdiTaxablePayroll: number;
  hiTaxablePayroll: number;
  gdp: number;
}

interface AllocationInput {
  reformName: string;
  revenueImpact: number;
  baselineTobOasdi: number;
  baselineTobMedicareHi: number;
  tobOasdiImpact: number;
  tobMedicareHiImpact: number;
  oasdiNetImpact: number;
  hiNetImpact: number;
}

interface AllocationResult {
  revenueImpact: number;
  tobOasdiImpact: number;
  tobMedicareHiImpact: number;
  tobTotalImpact: number;
}

const allocationEligibleOptions = new Set([
  "option1",
  "option2",
  "option8",
  "option9",
  "option10",
]);
const baselineShareOptions = new Set(["option3", "option4", "option11"]);
const netImpactOptions = new Set(["option5", "option6"]);
const directBranchingOptions = new Set(["option12", "option13", "option14_stacked"]);
const generalRevenueOptions = new Set(["option7"]);
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export const ALLOCATION_ELIGIBLE_OPTIONS = [...allocationEligibleOptions];

let projectionCache: Promise<Map<number, EconomicProjection>> | null = null;
const csvCache = new Map<string, Promise<string>>();

function asNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

async function fetchCsv(path: string): Promise<string> {
  const resolvedPath =
    path.startsWith("/") && basePath ? `${basePath}${path}` : path;
  if (!csvCache.has(path)) {
    csvCache.set(
      path,
      fetch(resolvedPath).then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to fetch ${resolvedPath}: ${response.status}`);
        }
        return response.text();
      }),
    );
  }
  return csvCache.get(path)!;
}

async function loadHiTaxablePayroll(): Promise<Map<number, number>> {
  const csvContent = await fetchCsv("/data/hi_taxable_payroll.csv");
  const parsed = Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
  });
  const payroll = new Map<number, number>();

  for (const row of parsed.data) {
    payroll.set(asNumber(row.year), asNumber(row.hi_taxable_payroll));
  }

  return payroll;
}

async function loadEconomicProjections(): Promise<Map<number, EconomicProjection>> {
  if (!projectionCache) {
    projectionCache = Promise.all([
      fetchCsv("/data/ssa_economic_projections.csv"),
      loadHiTaxablePayroll(),
    ]).then(([csvContent, hiTaxablePayroll]) => {
      const parsed = Papa.parse<Record<string, string>>(csvContent, {
        header: true,
        skipEmptyLines: true,
      });
      const projections = new Map<number, EconomicProjection>();

      for (const row of parsed.data) {
        const year = asNumber(row.year);
        const oasdiTaxablePayroll = asNumber(row.taxable_payroll);
        projections.set(year, {
          year,
          oasdiTaxablePayroll,
          hiTaxablePayroll: hiTaxablePayroll.get(year) ?? oasdiTaxablePayroll,
          gdp: asNumber(row.gdp),
        });
      }

      return projections;
    });
  }

  return projectionCache;
}

function splitRevenueImpacts(
  row: AllocationInput,
  allocationMode: AllocationMode,
): AllocationResult {
  if (generalRevenueOptions.has(row.reformName)) {
    return {
      revenueImpact: row.revenueImpact,
      tobOasdiImpact: 0,
      tobMedicareHiImpact: 0,
      tobTotalImpact: 0,
    };
  }

  if (directBranchingOptions.has(row.reformName)) {
    const revenueImpact = row.oasdiNetImpact + row.hiNetImpact;
    return {
      revenueImpact,
      tobOasdiImpact: row.oasdiNetImpact,
      tobMedicareHiImpact: row.hiNetImpact,
      tobTotalImpact: revenueImpact,
    };
  }

  const usesBaselineShares =
    baselineShareOptions.has(row.reformName) ||
    (allocationMode === "baselineShares" &&
      allocationEligibleOptions.has(row.reformName));

  if (usesBaselineShares) {
    const baselineTotal = row.baselineTobOasdi + row.baselineTobMedicareHi;
    if (baselineTotal <= 0) {
      return {
        revenueImpact: row.revenueImpact,
        tobOasdiImpact: 0,
        tobMedicareHiImpact: 0,
        tobTotalImpact: 0,
      };
    }

    const tobOasdiImpact =
      row.revenueImpact * (row.baselineTobOasdi / baselineTotal);
    return {
      revenueImpact: row.revenueImpact,
      tobOasdiImpact,
      tobMedicareHiImpact: row.revenueImpact - tobOasdiImpact,
      tobTotalImpact: row.revenueImpact,
    };
  }

  if (netImpactOptions.has(row.reformName)) {
    const revenueImpact = row.oasdiNetImpact + row.hiNetImpact;
    return {
      revenueImpact,
      tobOasdiImpact: row.oasdiNetImpact,
      tobMedicareHiImpact: row.hiNetImpact,
      tobTotalImpact: revenueImpact,
    };
  }

  const revenueImpact = row.tobOasdiImpact + row.tobMedicareHiImpact;
  return {
    revenueImpact,
    tobOasdiImpact: row.tobOasdiImpact,
    tobMedicareHiImpact: row.tobMedicareHiImpact,
    tobTotalImpact: revenueImpact,
  };
}

export async function loadDashboardData(
  _scoringType: ScoringType,
  allocationMode: AllocationMode,
): Promise<Record<string, YearlyImpact[]>> {
  const [csvContent, projections] = await Promise.all([
    fetchCsv("/data/all_static_results.csv"),
    loadEconomicProjections(),
  ]);

  const parsed = Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
  });

  const result: Record<string, YearlyImpact[]> = {};

  for (const row of parsed.data) {
    const reformName = row.reform_name ?? "";
    if (!reformName) continue;

    const year = asNumber(row.year);
    const allocationRow: AllocationInput = {
      reformName,
      revenueImpact: asNumber(row.revenue_impact),
      baselineTobOasdi: asNumber(row.baseline_tob_oasdi),
      baselineTobMedicareHi: asNumber(row.baseline_tob_medicare_hi),
      tobOasdiImpact: asNumber(row.tob_oasdi_impact),
      tobMedicareHiImpact: asNumber(row.tob_medicare_hi_impact),
      oasdiNetImpact: asNumber(row.oasdi_net_impact),
      hiNetImpact: asNumber(row.hi_net_impact),
    };
    const split = splitRevenueImpacts(allocationRow, allocationMode);
    const economicProjection = projections.get(year) ?? {
      year,
      oasdiTaxablePayroll: 0,
      hiTaxablePayroll: 0,
      gdp: 0,
    };

    const yearlyImpact: YearlyImpact = {
      year,
      revenueImpact: split.revenueImpact,
      tobOasdiImpact: split.tobOasdiImpact,
      tobMedicareHiImpact: split.tobMedicareHiImpact,
      tobTotalImpact: split.tobTotalImpact,
      baselineRevenue: asNumber(row.baseline_revenue),
      reformRevenue: asNumber(row.reform_revenue),
      baselineTobOasdi: allocationRow.baselineTobOasdi,
      baselineTobMedicareHi: allocationRow.baselineTobMedicareHi,
      baselineTobTotal:
        allocationRow.baselineTobOasdi + allocationRow.baselineTobMedicareHi,
      oasdiTaxablePayroll: economicProjection.oasdiTaxablePayroll,
      hiTaxablePayroll: economicProjection.hiTaxablePayroll,
      gdp: economicProjection.gdp,
      pctOfOasdiPayroll:
        economicProjection.oasdiTaxablePayroll > 0
          ? (split.revenueImpact / economicProjection.oasdiTaxablePayroll) * 100
          : 0,
      pctOfGdp:
        economicProjection.gdp > 0
          ? (split.revenueImpact / economicProjection.gdp) * 100
          : 0,
      oasdiPctOfPayroll:
        economicProjection.oasdiTaxablePayroll > 0
          ? (split.tobOasdiImpact / economicProjection.oasdiTaxablePayroll) * 100
          : 0,
      hiPctOfPayroll:
        economicProjection.hiTaxablePayroll > 0
          ? (split.tobMedicareHiImpact / economicProjection.hiTaxablePayroll) * 100
          : 0,
      oasdiPctOfGdp:
        economicProjection.gdp > 0
          ? (split.tobOasdiImpact / economicProjection.gdp) * 100
          : 0,
      hiPctOfGdp:
        economicProjection.gdp > 0
          ? (split.tobMedicareHiImpact / economicProjection.gdp) * 100
          : 0,
    };

    if (!result[reformName]) {
      result[reformName] = [];
    }
    result[reformName].push(yearlyImpact);
  }

  for (const impacts of Object.values(result)) {
    impacts.sort((left, right) => left.year - right.year);
  }

  return result;
}

export function calculateTotals(data: YearlyImpact[]) {
  const tenYearData = data.filter((row) => row.year >= 2026 && row.year <= 2035);
  const tenYear = tenYearData.reduce((sum, row) => sum + row.revenueImpact, 0);
  const total = data.reduce((sum, row) => sum + row.revenueImpact, 0);
  const tenYearPayroll = tenYearData.reduce(
    (sum, row) => sum + row.oasdiTaxablePayroll,
    0,
  );
  const tenYearGdp = tenYearData.reduce((sum, row) => sum + row.gdp, 0);
  const totalPayroll = data.reduce((sum, row) => sum + row.oasdiTaxablePayroll, 0);
  const totalGdp = data.reduce((sum, row) => sum + row.gdp, 0);

  return {
    tenYear,
    total,
    tenYearPctPayroll: tenYearPayroll > 0 ? (tenYear / tenYearPayroll) * 100 : 0,
    tenYearPctGdp: tenYearGdp > 0 ? (tenYear / tenYearGdp) * 100 : 0,
    totalPctPayroll: totalPayroll > 0 ? (total / totalPayroll) * 100 : 0,
    totalPctGdp: totalGdp > 0 ? (total / totalGdp) * 100 : 0,
  };
}

export function spotlightRows(data: YearlyImpact[]) {
  const spotlightYears = new Set([2026, 2030, 2035]);
  return data.filter((row) => spotlightYears.has(row.year));
}
