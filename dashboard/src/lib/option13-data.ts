import Papa from "papaparse";

export interface Option13Data {
  year: number;
  baselineSsBenefits: number;
  baselineIncomesTax: number;
  baselineSsGap: number;
  baselineHiGap: number;
  benefitMultiplier: number;
  newEmployeeSsRate: number;
  newEmployerSsRate: number;
  newEmployeeHiRate: number;
  newEmployerHiRate: number;
  reformSsBenefits: number;
  reformIncomeTax: number;
  reformSsGap: number;
  reformHiGap: number;
  benefitCut: number;
  incomeTaxImpact: number;
  tobOasdiImpact: number;
  tobHiImpact: number;
  rateIncreaseSsRevenue: number;
  rateIncreaseHiRevenue: number;
  totalRateIncreaseRevenue: number;
  ssRateIncreasePp: number;
  hiRateIncreasePp: number;
  tobOasdiLoss: number;
  tobHiLoss: number;
  ssGapAfter: number;
  hiGapAfter: number;
  totalGapAfter: number;
}

export interface TrusteesComparisonData {
  year: number;
  oasdiTaxablePayrollB: number;
  hiTaxablePayrollB: number;
  oasdiGapPct: number;
  trusteesOasdiGapB: number;
  peOasdiGapB: number | null;
  oasdiPeTrusteesRatio: number | null;
  hiGapPct: number;
  trusteesHiGapB: number;
  peHiGapB: number | null;
  hiPeTrusteesRatio: number | null;
}

function asNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

async function fetchCsv(path: string) {
  const resolvedPath =
    path.startsWith("/") && basePath ? `${basePath}${path}` : path;
  const response = await fetch(resolvedPath);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${resolvedPath}: ${response.status}`);
  }
  return response.text();
}

export async function loadOption13Data(): Promise<Option13Data[]> {
  const csvContent = await fetchCsv("/data/option13_balanced_fix.csv");
  const parsed = Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
  });

  return parsed.data
    .map((row) => ({
      year: asNumber(row.year),
      baselineSsBenefits: asNumber(row.baseline_ss_benefits),
      baselineIncomesTax: asNumber(row.baseline_income_tax),
      baselineSsGap: asNumber(row.baseline_ss_gap),
      baselineHiGap: asNumber(row.baseline_hi_gap),
      benefitMultiplier: asNumber(row.benefit_multiplier),
      newEmployeeSsRate: asNumber(row.new_employee_ss_rate),
      newEmployerSsRate: asNumber(row.new_employer_ss_rate),
      newEmployeeHiRate: asNumber(row.new_employee_hi_rate),
      newEmployerHiRate: asNumber(row.new_employer_hi_rate),
      reformSsBenefits: asNumber(row.reform_ss_benefits),
      reformIncomeTax: asNumber(row.reform_income_tax),
      reformSsGap: asNumber(row.reform_ss_gap),
      reformHiGap: asNumber(row.reform_hi_gap),
      benefitCut: asNumber(row.benefit_cut),
      incomeTaxImpact: asNumber(row.income_tax_impact),
      tobOasdiImpact: asNumber(row.tob_oasdi_impact),
      tobHiImpact: asNumber(row.tob_hi_impact),
      rateIncreaseSsRevenue: asNumber(row.rate_increase_ss_revenue),
      rateIncreaseHiRevenue: asNumber(row.rate_increase_hi_revenue),
      totalRateIncreaseRevenue: asNumber(row.total_rate_increase_revenue),
      ssRateIncreasePp: asNumber(row.ss_rate_increase_pp),
      hiRateIncreasePp: asNumber(row.hi_rate_increase_pp),
      tobOasdiLoss: asNumber(row.tob_oasdi_loss),
      tobHiLoss: asNumber(row.tob_hi_loss),
      ssGapAfter: asNumber(row.ss_gap_after),
      hiGapAfter: asNumber(row.hi_gap_after),
      totalGapAfter: asNumber(row.total_gap_after),
    }))
    .sort((a, b) => a.year - b.year);
}

export async function loadTrusteesComparisonData(): Promise<TrusteesComparisonData[]> {
  const [csvContent, option13Data] = await Promise.all([
    fetchCsv("/data/trustees_vs_pe_gaps_comparison.csv"),
    loadOption13Data(),
  ]);
  const parsed = Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
  });
  const option13ByYear = new Map(option13Data.map((row) => [row.year, row]));

  const nullableNumber = (value: unknown) => {
    if (value === "") return null;
    const numeric = asNumber(value);
    return Number.isFinite(numeric) ? numeric : null;
  };

  return parsed.data
    .map((row) => {
      const year = asNumber(row.year);
      const trusteesOasdiGapB = asNumber(row.trustees_oasdi_gap_B);
      const trusteesHiGapB = asNumber(row.trustees_hi_gap_B);
      const option13 = option13ByYear.get(year);
      const peOasdiGapB = option13
        ? Math.abs(option13.baselineSsGap) / 1e9
        : nullableNumber(row.pe_oasdi_gap_B);
      const peHiGapB = option13
        ? Math.abs(option13.baselineHiGap) / 1e9
        : nullableNumber(row.pe_hi_gap_B);

      return {
        year,
        oasdiTaxablePayrollB: asNumber(row.oasdi_taxable_payroll_B),
        hiTaxablePayrollB: asNumber(row.hi_taxable_payroll_B),
        oasdiGapPct: asNumber(row.oasdi_gap_pct),
        trusteesOasdiGapB,
        peOasdiGapB,
        oasdiPeTrusteesRatio:
          peOasdiGapB !== null && trusteesOasdiGapB !== 0
            ? peOasdiGapB / trusteesOasdiGapB
            : null,
        hiGapPct: asNumber(row.hi_gap_pct),
        trusteesHiGapB,
        peHiGapB,
        hiPeTrusteesRatio:
          peHiGapB !== null && trusteesHiGapB !== 0
            ? peHiGapB / trusteesHiGapB
            : null,
      };
    })
    .sort((a, b) => a.year - b.year);
}
