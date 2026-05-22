import Papa from "papaparse";

export interface BalancedFixRow {
  year: number;
  baselineSsGapBillions: number;
  baselineHiGapBillions: number;
  benefitMultiplier: number;
  benefitCutBillions: number;
  benefitCutPct: number;
  employeeSsRatePct: number;
  employerSsRatePct: number;
  combinedSsRatePct: number;
  employeeHiRatePct: number;
  employerHiRatePct: number;
  combinedHiRatePct: number;
  ssRateIncreasePp: number;
  hiRateIncreasePp: number;
  incomeTaxImpactBillions: number;
  tobOasdiImpactBillions: number;
  tobHiImpactBillions: number;
  rateIncreaseSsRevenueBillions: number;
  rateIncreaseHiRevenueBillions: number;
  totalRateIncreaseRevenueBillions: number;
  ssGapAfterMillions: number;
  hiGapAfterMillions: number;
  totalGapAfterMillions: number;
  scenarioH5Uri: string;
  metadataUri: string;
  completionUri: string;
  outputH5Sha256: string;
  source: string;
}

export interface BalancedFixMetadata {
  schema: string;
  generated_at: string;
  source_path: string;
  recovered_dir: string;
  output_path: string;
  run_prefix: string;
  reform_id: string;
  source_result_count: number;
  years: number[];
  full_reform_h5_saved: boolean;
  object_store_upload_validated: boolean;
  raw_h5_persistence: string;
  manual_weight_aggregation_used: boolean;
  baseline_aggregate_metrics_computed_before_h5_save: boolean;
  unit_conversion: string;
  interpolation_used: boolean;
  support_gate_override: string;
  max_abs_total_gap_after_millions: number;
  runtime_packages: Record<string, string | null>;
}

export interface BalancedFixData {
  rows: BalancedFixRow[];
  metadata: BalancedFixMetadata;
}

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const textCache = new Map<string, Promise<string>>();
const BALANCED_FIX_CSV = "/data/balanced_fix_baseline.csv";
const BALANCED_FIX_METADATA = "/data/balanced_fix_baseline_metadata.json";

function asNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function resolvedPath(path: string) {
  return path.startsWith("/") && basePath ? `${basePath}${path}` : path;
}

async function fetchText(path: string): Promise<string> {
  if (!textCache.has(path)) {
    const resolved = resolvedPath(path);
    textCache.set(
      path,
      fetch(resolved).then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to fetch ${resolved}: ${response.status}`);
        }
        return response.text();
      }),
    );
  }
  return textCache.get(path)!;
}

async function fetchJson<T>(path: string): Promise<T> {
  const resolved = resolvedPath(path);
  const response = await fetch(resolved);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${resolved}: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function parseBalancedFixRow(row: Record<string, string>): BalancedFixRow {
  return {
    year: asNumber(row.year),
    baselineSsGapBillions: asNumber(row.baseline_ss_gap_billions),
    baselineHiGapBillions: asNumber(row.baseline_hi_gap_billions),
    benefitMultiplier: asNumber(row.benefit_multiplier),
    benefitCutBillions: asNumber(row.benefit_cut_billions),
    benefitCutPct: asNumber(row.benefit_cut_pct),
    employeeSsRatePct: asNumber(row.employee_ss_rate_pct),
    employerSsRatePct: asNumber(row.employer_ss_rate_pct),
    combinedSsRatePct: asNumber(row.combined_ss_rate_pct),
    employeeHiRatePct: asNumber(row.employee_hi_rate_pct),
    employerHiRatePct: asNumber(row.employer_hi_rate_pct),
    combinedHiRatePct: asNumber(row.combined_hi_rate_pct),
    ssRateIncreasePp: asNumber(row.ss_rate_increase_pp),
    hiRateIncreasePp: asNumber(row.hi_rate_increase_pp),
    incomeTaxImpactBillions: asNumber(row.income_tax_impact_billions),
    tobOasdiImpactBillions: asNumber(row.tob_oasdi_impact_billions),
    tobHiImpactBillions: asNumber(row.tob_hi_impact_billions),
    rateIncreaseSsRevenueBillions: asNumber(
      row.rate_increase_ss_revenue_billions,
    ),
    rateIncreaseHiRevenueBillions: asNumber(
      row.rate_increase_hi_revenue_billions,
    ),
    totalRateIncreaseRevenueBillions: asNumber(
      row.total_rate_increase_revenue_billions,
    ),
    ssGapAfterMillions: asNumber(row.ss_gap_after_millions),
    hiGapAfterMillions: asNumber(row.hi_gap_after_millions),
    totalGapAfterMillions: asNumber(row.total_gap_after_millions),
    scenarioH5Uri: row.scenario_h5_uri ?? "",
    metadataUri: row.metadata_uri ?? "",
    completionUri: row.completion_uri ?? "",
    outputH5Sha256: row.output_h5_sha256 ?? "",
    source: row.source ?? "",
  };
}

export function balancedFixDataHref(path: string) {
  return resolvedPath(path);
}

export async function loadBalancedFixData(): Promise<BalancedFixData> {
  const [csvContent, metadata] = await Promise.all([
    fetchText(BALANCED_FIX_CSV),
    fetchJson<BalancedFixMetadata>(BALANCED_FIX_METADATA),
  ]);
  const parsed = Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
  });
  const rows = parsed.data
    .map(parseBalancedFixRow)
    .sort((left, right) => left.year - right.year);
  return { rows, metadata };
}
