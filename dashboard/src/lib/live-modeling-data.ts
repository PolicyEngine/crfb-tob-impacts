import Papa from "papaparse";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const csvCache = new Map<string, Promise<string>>();

export interface LiveModelingMetadata {
  generated_at?: string;
  selected_year_count?: number;
  selected_cell_count?: number;
  standard_reform_count?: number;
  baseline_ready_year_count?: number;
  reform_h5_complete_or_sentinel_count?: number;
  reform_h5_pending_count?: number;
  baseline_results_csv?: string;
  reform_status_csv?: string;
  notes?: string[];
}

export interface LiveBaselineResult {
  year: number;
  baselineH5Status: string;
  runId: string;
  sourceSha: string;
  targetSourceName: string;
  calibrationQuality: string;
  validationPassed: boolean;
  maxConstraintPctError: number;
  ageMaxPctError: number;
  effectiveSampleSize: number;
  top10WeightSharePct: number;
  top100WeightSharePct: number;
  negativeWeightPct: number;
  h5SocialSecurityB: number;
  h5OasdiTaxablePayrollB: number;
  h5TobOasdiB: number;
  h5TobHiB: number;
  h5TobTotalB: number;
  supportAugmentation: string;
  metadataPath: string;
  dashboardTobOasdiB: number;
  dashboardTobHiB: number;
  dashboardTobTotalB: number;
  gdpB: number;
  federalIncomeTaxB: number;
}

export interface LiveReformStatus {
  reformName: string;
  year: number;
  scoringType: string;
  baselineH5Status: string;
  reformH5Status: string;
  aggregateStatus: string;
  callId: string;
  dashboardUrl: string;
  error: string;
  scenarioH5Uri: string;
  metadataUri: string;
  outputH5Sha256: string;
  durationSeconds: number;
}

export interface LiveModelingData {
  metadata: LiveModelingMetadata;
  baseline: LiveBaselineResult[];
  reformStatus: LiveReformStatus[];
}

function asNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function asBoolean(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value.toLowerCase() === "true";
  return false;
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

async function fetchJson<T>(path: string): Promise<T> {
  const resolvedPath =
    path.startsWith("/") && basePath ? `${basePath}${path}` : path;
  const response = await fetch(resolvedPath);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${resolvedPath}: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function parseCsvRows<T>(
  csvContent: string,
  mapper: (row: Record<string, string>) => T,
): T[] {
  const parsed = Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
  });
  return parsed.data.map(mapper);
}

export async function loadLiveModelingData(): Promise<LiveModelingData> {
  const [metadata, baselineCsv, reformStatusCsv] = await Promise.all([
    fetchJson<LiveModelingMetadata>("/data/live_modeling_status_metadata.json"),
    fetchCsv("/data/live_baseline_results.csv"),
    fetchCsv("/data/live_reform_status.csv"),
  ]);

  const baseline = parseCsvRows<LiveBaselineResult>(baselineCsv, (row) => ({
    year: asNumber(row.year),
    baselineH5Status: row.baseline_h5_status ?? "",
    runId: row.run_id ?? "",
    sourceSha: row.source_sha ?? "",
    targetSourceName: row.target_source_name ?? "",
    calibrationQuality: row.calibration_quality ?? "",
    validationPassed: asBoolean(row.validation_passed),
    maxConstraintPctError: asNumber(row.max_constraint_pct_error),
    ageMaxPctError: asNumber(row.age_max_pct_error),
    effectiveSampleSize: asNumber(row.effective_sample_size),
    top10WeightSharePct: asNumber(row.top_10_weight_share_pct),
    top100WeightSharePct: asNumber(row.top_100_weight_share_pct),
    negativeWeightPct: asNumber(row.negative_weight_pct),
    h5SocialSecurityB: asNumber(row.h5_social_security_b),
    h5OasdiTaxablePayrollB: asNumber(row.h5_oasdi_taxable_payroll_b),
    h5TobOasdiB: asNumber(row.h5_tob_oasdi_b),
    h5TobHiB: asNumber(row.h5_tob_hi_b),
    h5TobTotalB: asNumber(row.h5_tob_total_b),
    supportAugmentation: row.support_augmentation ?? "",
    metadataPath: row.metadata_path ?? "",
    dashboardTobOasdiB: asNumber(row.tob_oasdi),
    dashboardTobHiB: asNumber(row.tob_hi),
    dashboardTobTotalB: asNumber(row.tob_total),
    gdpB: asNumber(row.gdp),
    federalIncomeTaxB: asNumber(row.federal_income_tax),
  }));

  const reformStatus = parseCsvRows<LiveReformStatus>(reformStatusCsv, (row) => ({
    reformName: row.reform_name ?? "",
    year: asNumber(row.year),
    scoringType: row.scoring_type ?? "",
    baselineH5Status: row.baseline_h5_status ?? "",
    reformH5Status: row.reform_h5_status ?? "",
    aggregateStatus: row.aggregate_status ?? "",
    callId: row.call_id ?? "",
    dashboardUrl: row.dashboard_url ?? "",
    error: row.error ?? "",
    scenarioH5Uri: row.scenario_h5_uri ?? "",
    metadataUri: row.metadata_uri ?? "",
    outputH5Sha256: row.output_h5_sha256 ?? "",
    durationSeconds: asNumber(row.duration_seconds),
  }));

  return { metadata, baseline, reformStatus };
}
