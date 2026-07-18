import Papa from "papaparse";

export type ScoringType = "static" | "behavioral";
export type AllocationMode =
  | "currentLaw"
  | "baselineShares"
  | "allOasdi"
  | "allHi";
export type DisplayUnit = "dollars" | "pctPayroll" | "pctGdp";
export type BaselineScenario = "currentLaw" | "ssSolvent";

export interface YearlyImpact {
  year: number;
  revenueImpact: number;
  tobOasdiImpact: number;
  tobMedicareHiImpact: number;
  tobTotalImpact: number;
  generalFundImpact: number;
  baselineRevenue: number;
  reformRevenue: number;
  baselineTobOasdi: number;
  baselineTobMedicareHi: number;
  baselineTobTotal: number;
  oasdiTaxablePayroll: number;
  hiTaxablePayroll: number;
  gdp: number;
  discountFactor: number;
  hiDiscountFactor: number;
  pctOfOasdiPayroll: number;
  pctOfGdp: number;
  oasdiPctOfPayroll: number;
  hiPctOfPayroll: number;
  generalFundPctOfPayroll: number;
  oasdiPctOfGdp: number;
  hiPctOfGdp: number;
  generalFundPctOfGdp: number;
}

interface EconomicProjection {
  year: number;
  oasdiTaxablePayroll: number;
  hiTaxablePayroll: number;
  gdp: number;
  discountFactor: number;
  hiDiscountFactor: number;
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

// Benefit-taxation reforms that default to maintaining the baseline
// trust-fund shares (CRFB's rule for every option except the Roth-structure
// ones and option 7). tax93 joined the model after that rule was set and
// must follow it like its 90%/95% siblings.
const allocationEligibleOptions = new Set([
  "option1",
  "option2",
  "option8",
  "option9",
  "option10",
  "tax93",
  "magi100",
  "tax_panel_2005",
]);
const baselineShareOptions = new Set(["option3", "option4", "option11"]);
const netImpactOptions = new Set(["option5", "option6"]);
const directBranchingOptions = new Set(["option12"]);
// Reforms whose general-revenue cost is attributed entirely to OASDI rather
// than shown as a separate general-fund line. Reverse Roth makes the employee
// OASDI payroll tax deductible, so its income-tax cost belongs to OASDI;
// Medicare is left unchanged.
const generalFundToOasdiOptions = new Set(["reverse_roth"]);
const balancedFixEligibleOptions = new Set([
  "option1",
  "option2",
  "option8",
  "option12",
]);
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

// Stamped into the CSV export so consumers can see at a glance whether a
// download came from a stale browser tab. Bump when the published data
// changes; a test pins it to the results contract's generation date.
export const DATA_VINTAGE = "2026-07-17";

export const BALANCED_FIX_ELIGIBLE_OPTIONS = [...balancedFixEligibleOptions];

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
          throw new Error(
            `Failed to fetch ${resolvedPath}: ${response.status}`,
          );
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

async function loadDiscountFactors(): Promise<{
  oasdi: Map<number, number>;
  hi: Map<number, number>;
}> {
  // Present-value discount factors to the start of 2026 using each trust
  // fund's Trustees effective interest rates: OASDI from the TR2026 Table
  // VI.G1 compound effective trust-fund interest factors, HI from Medicare
  // Trustees Table IV.A4 (graded to the 4.7% ultimate nominal rate by 2040).
  // Each year's flow is discounted by the cumulative product of (1 + rate)
  // for its own fund.
  const csvContent = await fetchCsv("/data/effective_interest_rates.csv");
  const parsed = Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
  });
  const rows = parsed.data
    .map((row) => ({
      year: asNumber(row.year),
      oasdi: asNumber(row.oasdi_effective_rate_pct) / 100,
      hi: asNumber(row.hi_effective_rate_pct) / 100,
    }))
    .sort((a, b) => a.year - b.year);
  const oasdi = new Map<number, number>();
  const hi = new Map<number, number>();
  let oasdiCumulative = 1;
  let hiCumulative = 1;
  for (const row of rows) {
    oasdiCumulative /= 1 + row.oasdi;
    hiCumulative /= 1 + row.hi;
    oasdi.set(row.year, oasdiCumulative);
    hi.set(row.year, hiCumulative);
  }
  return { oasdi, hi };
}

async function loadEconomicProjections(): Promise<
  Map<number, EconomicProjection>
> {
  if (!projectionCache) {
    projectionCache = Promise.all([
      fetchCsv("/data/ssa_economic_projections.csv"),
      loadHiTaxablePayroll(),
      loadDiscountFactors(),
    ]).then(([csvContent, hiTaxablePayroll, discountFactors]) => {
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
          discountFactor: discountFactors.oasdi.get(year) ?? 1,
          hiDiscountFactor: discountFactors.hi.get(year) ?? 1,
        });
      }

      return projections;
    });
  }

  return projectionCache;
}

// The single-trust-fund override modes ("all OASDI" / "all HI") assign a
// reform's WHOLE revenue impact to one trust fund. They apply to every reform,
// so they use each reform's native revenue total — which for the structural
// swaps is the branched net-impact sum, not the raw revenue_impact column.
function nativeRevenueImpact(row: AllocationInput): number {
  if (
    directBranchingOptions.has(row.reformName) ||
    netImpactOptions.has(row.reformName)
  ) {
    return row.oasdiNetImpact + row.hiNetImpact;
  }
  return row.revenueImpact;
}

function splitRevenueImpacts(
  row: AllocationInput,
  allocationMode: AllocationMode,
): AllocationResult {
  // "All OASDI" / "All HI" override every reform: the entire native revenue
  // impact lands on one trust fund, with no general-fund residual. For the
  // structural swaps (option12, reverse Roth) "the whole impact" is the
  // reform's branched net revenue, not the small benefit-taxation column.
  if (allocationMode === "allOasdi") {
    const revenueImpact = nativeRevenueImpact(row);
    return {
      revenueImpact,
      tobOasdiImpact: revenueImpact,
      tobMedicareHiImpact: 0,
      tobTotalImpact: revenueImpact,
    };
  }

  if (allocationMode === "allHi") {
    const revenueImpact = nativeRevenueImpact(row);
    return {
      revenueImpact,
      tobOasdiImpact: 0,
      tobMedicareHiImpact: revenueImpact,
      tobTotalImpact: revenueImpact,
    };
  }

  if (directBranchingOptions.has(row.reformName)) {
    // The direct-branching swap (option 12) is scored straight from its OASDI
    // and HI net-impact columns. This IS its statutory split, so both the
    // default ("baseline shares") and the "current law" statutory mode keep it.
    const revenueImpact = row.oasdiNetImpact + row.hiNetImpact;
    return {
      revenueImpact,
      tobOasdiImpact: row.oasdiNetImpact,
      tobMedicareHiImpact: row.hiNetImpact,
      tobTotalImpact: revenueImpact,
    };
  }

  if (generalFundToOasdiOptions.has(row.reformName)) {
    // Fold the general-revenue cost (the employee OASDI payroll-tax deduction)
    // into OASDI; leave the benefit-taxation HI share as scored. The whole
    // revenue impact is then split across the trust funds with no general-fund
    // line. This is reverse Roth's mechanism split, so the default and the
    // "current law" statutory mode both keep it (only the all-OASDI / all-HI
    // overrides above reassign it).
    const generalFundDelta =
      row.revenueImpact - (row.tobOasdiImpact + row.tobMedicareHiImpact);
    return {
      revenueImpact: row.revenueImpact,
      tobOasdiImpact: row.tobOasdiImpact + generalFundDelta,
      tobMedicareHiImpact: row.tobMedicareHiImpact,
      tobTotalImpact: row.revenueImpact,
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

  // "Current law" statutory mode (and any non-eligible reform under the default
  // mode): split by the scored statutory OASDI/HI columns, leaving the rest as
  // a general-fund residual.
  return {
    revenueImpact: row.revenueImpact,
    tobOasdiImpact: row.tobOasdiImpact,
    tobMedicareHiImpact: row.tobMedicareHiImpact,
    tobTotalImpact: row.tobOasdiImpact + row.tobMedicareHiImpact,
  };
}

export async function loadDashboardData(
  scoringType: ScoringType,
  allocationMode: AllocationMode,
  baselineScenario: BaselineScenario = "currentLaw",
): Promise<Record<string, YearlyImpact[]>> {
  const projections = await loadEconomicProjections();

  // Gather the rows to score. Under the SS-solvent baseline the options still
  // start in 2026: the solvency fix only diverges from current law from 2035,
  // so 2026-2034 are scored against current law (spliced from results.csv) and
  // 2035-2100 against the solvent baseline.
  const SOLVENT_START_YEAR = 2035;
  const parse = (csv: string) =>
    Papa.parse<Record<string, string>>(csv, {
      header: true,
      skipEmptyLines: true,
    }).data;
  const sourced: { row: Record<string, string>; isSolvent: boolean }[] = [];
  if (baselineScenario === "ssSolvent") {
    const [solventCsv, currentLawCsv] = await Promise.all([
      fetchCsv("/data/balanced_fix_results.csv"),
      fetchCsv("/data/results.csv"),
    ]);
    for (const row of parse(solventCsv)) {
      if (row.baseline_scenario === "ss_solvent") {
        sourced.push({ row, isSolvent: true });
      }
    }
    for (const row of parse(currentLawCsv)) {
      if (
        asNumber(row.year) < SOLVENT_START_YEAR &&
        balancedFixEligibleOptions.has(row.reform_name ?? "")
      ) {
        sourced.push({ row, isSolvent: false });
      }
    }
  } else {
    for (const row of parse(await fetchCsv("/data/results.csv"))) {
      sourced.push({ row, isSolvent: false });
    }
  }

  const result: Record<string, YearlyImpact[]> = {};

  for (const { row, isSolvent } of sourced) {
    if ((row.scoring_type ?? "") !== scoringType) continue;

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
    const split =
      isSolvent
        ? {
            revenueImpact: asNumber(row.revenue_impact),
            tobOasdiImpact: asNumber(row.solvent_oasdi_impact),
            tobMedicareHiImpact: asNumber(row.solvent_medicare_hi_impact),
            tobTotalImpact:
              asNumber(row.solvent_oasdi_impact) +
              asNumber(row.solvent_medicare_hi_impact),
            generalFundImpact: asNumber(row.solvent_general_fund_impact),
          }
        : splitRevenueImpacts(
            allocationRow,
            // The 2026-2034 rows spliced into the solvency view use a fixed
            // baseline-share split — the trust-fund allocation toggle is hidden
            // under solvency, so a stale allocationMode must not leak in. The
            // live allocationMode applies only to the current-law scenario.
            baselineScenario === "ssSolvent" ? "baselineShares" : allocationMode,
          );
    const generalFundImpact =
      "generalFundImpact" in split
        ? split.generalFundImpact
        : split.revenueImpact - split.tobTotalImpact;
    const economicProjection = projections.get(year) ?? {
      year,
      oasdiTaxablePayroll: 0,
      hiTaxablePayroll: 0,
      gdp: 0,
      discountFactor: 1,
      hiDiscountFactor: 1,
    };

    const yearlyImpact: YearlyImpact = {
      year,
      revenueImpact: split.revenueImpact,
      tobOasdiImpact: split.tobOasdiImpact,
      tobMedicareHiImpact: split.tobMedicareHiImpact,
      tobTotalImpact: split.tobTotalImpact,
      generalFundImpact,
      baselineRevenue: asNumber(row.baseline_revenue),
      reformRevenue: asNumber(row.reform_revenue),
      baselineTobOasdi: allocationRow.baselineTobOasdi,
      baselineTobMedicareHi: allocationRow.baselineTobMedicareHi,
      baselineTobTotal:
        allocationRow.baselineTobOasdi + allocationRow.baselineTobMedicareHi,
      oasdiTaxablePayroll: economicProjection.oasdiTaxablePayroll,
      hiTaxablePayroll: economicProjection.hiTaxablePayroll,
      gdp: economicProjection.gdp,
      discountFactor: economicProjection.discountFactor,
      hiDiscountFactor: economicProjection.hiDiscountFactor,
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
          ? (split.tobOasdiImpact / economicProjection.oasdiTaxablePayroll) *
            100
          : 0,
      hiPctOfPayroll:
        economicProjection.hiTaxablePayroll > 0
          ? (split.tobMedicareHiImpact / economicProjection.hiTaxablePayroll) *
            100
          : 0,
      generalFundPctOfPayroll:
        economicProjection.oasdiTaxablePayroll > 0
          ? (generalFundImpact / economicProjection.oasdiTaxablePayroll) * 100
          : 0,
      oasdiPctOfGdp:
        economicProjection.gdp > 0
          ? (split.tobOasdiImpact / economicProjection.gdp) * 100
          : 0,
      hiPctOfGdp:
        economicProjection.gdp > 0
          ? (split.tobMedicareHiImpact / economicProjection.gdp) * 100
          : 0,
      generalFundPctOfGdp:
        economicProjection.gdp > 0
          ? (generalFundImpact / economicProjection.gdp) * 100
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
  const tenYearData = data.filter(
    (row) => row.year >= 2026 && row.year <= 2035,
  );
  const tenYear = tenYearData.reduce((sum, row) => sum + row.revenueImpact, 0);
  const total = data.reduce((sum, row) => sum + row.revenueImpact, 0);
  const tenYearPayroll = tenYearData.reduce(
    (sum, row) => sum + row.oasdiTaxablePayroll,
    0,
  );
  const tenYearGdp = tenYearData.reduce((sum, row) => sum + row.gdp, 0);
  const totalPayroll = data.reduce(
    (sum, row) => sum + row.oasdiTaxablePayroll,
    0,
  );
  const totalGdp = data.reduce((sum, row) => sum + row.gdp, 0);

  // Per-trust-fund cumulative impact, each over its OWN taxable-payroll base.
  // OASDI payroll is capped; HI payroll is uncapped — different denominators,
  // so the two are never mixed on a single "% of payroll" axis.
  const sumBy = (rows: YearlyImpact[], key: keyof YearlyImpact) =>
    rows.reduce((acc, row) => acc + (row[key] as number), 0);
  const totalOasdi = sumBy(data, "tobOasdiImpact");
  const totalHi = sumBy(data, "tobMedicareHiImpact");
  const tenYearOasdi = sumBy(tenYearData, "tobOasdiImpact");
  const tenYearHi = sumBy(tenYearData, "tobMedicareHiImpact");
  const totalHiPayroll = sumBy(data, "hiTaxablePayroll");
  const tenYearHiPayroll = sumBy(tenYearData, "hiTaxablePayroll");

  // Present value to the start of 2026 at the TR2026 assumed nominal trust-fund
  // interest rates (standard trust-fund accounting). Each row carries its
  // cumulative discount factor; % figures discount numerator and denominator
  // alike (the 75-year summarized-rate convention).
  const pvBy = (
    rows: YearlyImpact[],
    key: keyof YearlyImpact,
    factorKey: "discountFactor" | "hiDiscountFactor" = "discountFactor",
  ) =>
    rows.reduce(
      (acc, row) => acc + (row[key] as number) * (row[factorKey] as number),
      0,
    );
  // Each fund's flows discount at its own effective rates (OASDI: TR2026
  // VI.G1; HI: Medicare IV.A4 graded to the 4.7% ultimate). General-fund
  // flows and the economy-wide denominators use the OASDI series. The
  // 75-year total is the sum of the discounted components, so the summary
  // figures stay additive.
  const pvOasdi = pvBy(data, "tobOasdiImpact");
  const pvHi = pvBy(data, "tobMedicareHiImpact", "hiDiscountFactor");
  const pvGeneralFund = pvBy(data, "generalFundImpact");
  const pvTotal = pvOasdi + pvHi + pvGeneralFund;
  const pvPayroll = pvBy(data, "oasdiTaxablePayroll");
  const pvHiPayroll = pvBy(data, "hiTaxablePayroll", "hiDiscountFactor");
  const pvGdp = pvBy(data, "gdp");

  return {
    tenYear,
    total,
    tenYearPctPayroll:
      tenYearPayroll > 0 ? (tenYear / tenYearPayroll) * 100 : 0,
    tenYearPctGdp: tenYearGdp > 0 ? (tenYear / tenYearGdp) * 100 : 0,
    totalPctPayroll: totalPayroll > 0 ? (total / totalPayroll) * 100 : 0,
    totalPctGdp: totalGdp > 0 ? (total / totalGdp) * 100 : 0,
    totalOasdi,
    totalHi,
    tenYearOasdi,
    tenYearHi,
    totalOasdiPctPayroll:
      totalPayroll > 0 ? (totalOasdi / totalPayroll) * 100 : 0,
    totalHiPctPayroll:
      totalHiPayroll > 0 ? (totalHi / totalHiPayroll) * 100 : 0,
    tenYearOasdiPctPayroll:
      tenYearPayroll > 0 ? (tenYearOasdi / tenYearPayroll) * 100 : 0,
    tenYearHiPctPayroll:
      tenYearHiPayroll > 0 ? (tenYearHi / tenYearHiPayroll) * 100 : 0,
    pvTotal,
    pvOasdi,
    pvHi,
    pvTotalPctPayroll: pvPayroll > 0 ? (pvTotal / pvPayroll) * 100 : 0,
    pvTotalPctGdp: pvGdp > 0 ? (pvTotal / pvGdp) * 100 : 0,
    pvOasdiPctPayroll: pvPayroll > 0 ? (pvOasdi / pvPayroll) * 100 : 0,
    pvHiPctPayroll: pvHiPayroll > 0 ? (pvHi / pvHiPayroll) * 100 : 0,
    pvOasdiPctGdp: pvGdp > 0 ? (pvOasdi / pvGdp) * 100 : 0,
    pvHiPctGdp: pvGdp > 0 ? (pvHi / pvGdp) * 100 : 0,
  };
}

export function spotlightRows(
  data: YearlyImpact[],
  viewMode: "10year" | "75year" = "75year",
) {
  const spotlightYears =
    viewMode === "10year"
      ? new Set([2026, 2030, 2035])
      : new Set([2026, 2035, 2050, 2075, 2100]);
  return data.filter((row) => spotlightYears.has(row.year));
}
