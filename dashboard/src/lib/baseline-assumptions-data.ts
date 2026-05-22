import Papa from "papaparse";

export interface BaselineAggregate {
  year: number;
  federalIncomeTax: number;
  tobOasdi: number;
  tobHi: number;
  tobTotal: number;
  currentLawTobOasdi: number;
  currentLawTobHi: number;
  currentLawTobTotal: number;
  postObbbaTobDelta: number;
  oasdiNominalDeltaBillions: number;
  oasdiTaxablePayroll: number;
  hiTaxablePayroll: number;
  gdp: number;
  tobTotalPctOasdiPayroll: number;
  tobOasdiPctOasdiPayroll: number;
  tobHiPctHiPayroll: number;
  federalIncomeTaxPctGdp: number;
  calibrationTarget: string;
  calibrationQuality: string;
  hiMethod: string;
  oasdiSource: string;
  hiSource: string;
  currentLawSource: string;
  notes: string;
  taxAssumption: string;
  scenarioId: string;
  baselineKind: string;
  baselineSha256: string;
  baselineManifest: string;
}

export interface IndexedParameterSummary {
  parameterGroup: string;
  parameterGroupLabel: string;
  parameterName: string;
  parameterLabel: string;
  upratingParameter: string;
  rounding: string;
  values: Record<number, number>;
  growth2026To2100Pct: number;
}

export interface IndexedParameterAnnualValue {
  parameterGroup: string;
  parameterGroupLabel: string;
  parameterName: string;
  parameterLabel: string;
  upratingParameter: string;
  rounding: string;
  year: number;
  value: number;
}

export interface IndexingGrowth {
  year: number;
  indexingSource: string;
  growthRatePct: number;
}

export interface BaselineCalibrationTarget {
  year: number;
  datasetPath: string;
  targetSourceName: string;
  targetSourceSha256: string;
  taxAssumptionName: string;
  constraintName: string;
  constraintLabel: string;
  constraintGroup: string;
  constraintClassification: string;
  scoringContract: string;
  source: string;
  target: number;
  achieved: number;
  error: number;
  pctError: number;
  usedInYearRunnerReconciliation: boolean;
  unit: string;
}

export interface BaselineCalibrationDiagnostic {
  year: number;
  diagnosticId: string;
  diagnosticLabel: string;
  diagnosticGroup: string;
  value: number;
  unit: string;
  source: string;
  datasetPath: string;
  status: string;
}

export interface BaselinePolicyParameter {
  year: number;
  parameterName: string;
  parameterLabel: string;
  parameterGroup: string;
  baselineValue: string;
  baselineNumericValue: number;
  baselineValueType: string;
  touchedByReforms: string[];
  touchedByScoringTypes: string[];
  policyRole: string;
}

export interface BaselineReformParameter {
  reformName: string;
  scoringType: string;
  parameterName: string;
  parameterLabel: string;
  parameterGroup: string;
  period: string;
  value: string;
  numericValue: number;
  valueType: string;
  policyRole: string;
  affectsBaseline: boolean;
}

export interface BaselineAssumptionsMetadata {
  generated_at?: string;
  source_static_results?: string;
  source_post_obbba_tob_baseline?: string;
  source_post_obbba_tob_baseline_manifest?: string;
  public_post_obbba_tob_baseline_manifest?: string;
  post_obbba_tob_baseline_sha256?: string;
  scenario_id?: string;
  baseline_kind?: string;
  not_law?: boolean;
  law_mode?: string;
  hi_bridge_method?: string;
  tax_assumption?: {
    name?: string;
    description?: string;
    source?: string;
    start_year?: number;
    parameter_groups?: string[];
  };
  policyengine_version?: string;
  policyengine_us_version?: string;
  policyengine_core_version?: string;
  policyengine_packages?: Record<
    string,
    {
      distribution?: string;
      version?: string;
      source?: string;
      direct_url_present?: boolean;
      editable?: boolean;
    }
  >;
  indexed_parameter_count?: number;
  indexed_parameter_groups?: string[];
  calibration_target_count?: number;
  calibration_diagnostic_count?: number;
  policy_parameter_count?: number;
  reform_parameter_count?: number;
  calibration_metadata_roots?: string[];
  note?: string;
}

export interface BaselineAssumptionsData {
  aggregates: BaselineAggregate[];
  indexedParameters: IndexedParameterSummary[];
  indexedParameterValues: IndexedParameterAnnualValue[];
  indexingGrowth: IndexingGrowth[];
  calibrationTargets: BaselineCalibrationTarget[];
  calibrationDiagnostics: BaselineCalibrationDiagnostic[];
  policyParameters: BaselinePolicyParameter[];
  reformParameters: BaselineReformParameter[];
  metadata: BaselineAssumptionsMetadata;
}

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const csvCache = new Map<string, Promise<string>>();

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
  if (typeof value === "string") {
    return ["1", "true", "yes"].includes(value.trim().toLowerCase());
  }
  return false;
}

function splitList(value: string | undefined): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function fetchText(path: string): Promise<string> {
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

async function parseCsvRows(path: string) {
  const csvContent = await fetchText(path);
  return Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
  }).data;
}

function parseAggregate(row: Record<string, string>): BaselineAggregate {
  return {
    year: asNumber(row.year),
    federalIncomeTax: asNumber(row.federal_income_tax),
    tobOasdi: asNumber(row.tob_oasdi),
    tobHi: asNumber(row.tob_hi),
    tobTotal: asNumber(row.tob_total),
    currentLawTobOasdi: asNumber(row.current_law_tob_oasdi),
    currentLawTobHi: asNumber(row.current_law_tob_hi),
    currentLawTobTotal: asNumber(row.current_law_tob_total),
    postObbbaTobDelta: asNumber(row.post_obbba_tob_delta),
    oasdiNominalDeltaBillions: asNumber(row.oasdi_nominal_delta_billions),
    oasdiTaxablePayroll: asNumber(row.oasdi_taxable_payroll),
    hiTaxablePayroll: asNumber(row.hi_taxable_payroll),
    gdp: asNumber(row.gdp),
    tobTotalPctOasdiPayroll: asNumber(row.tob_total_pct_oasdi_payroll),
    tobOasdiPctOasdiPayroll: asNumber(row.tob_oasdi_pct_oasdi_payroll),
    tobHiPctHiPayroll: asNumber(row.tob_hi_pct_hi_payroll),
    federalIncomeTaxPctGdp: asNumber(row.federal_income_tax_pct_gdp),
    calibrationTarget: row.calibration_target ?? "",
    calibrationQuality: row.calibration_quality ?? "",
    hiMethod: row.hi_method ?? "",
    oasdiSource: row.oasdi_source ?? "",
    hiSource: row.hi_source ?? "",
    currentLawSource: row.current_law_source ?? "",
    notes: row.notes ?? "",
    taxAssumption: row.tax_assumption ?? "",
    scenarioId: row.scenario_id ?? "",
    baselineKind: row.baseline_kind ?? "",
    baselineSha256: row.baseline_sha256 ?? "",
    baselineManifest: row.baseline_manifest ?? "",
  };
}

function parseIndexedParameter(
  row: Record<string, string>,
): IndexedParameterSummary {
  const years = [2026, 2034, 2035, 2036, 2050, 2075, 2100];
  return {
    parameterGroup: row.parameter_group ?? "",
    parameterGroupLabel: row.parameter_group_label ?? "",
    parameterName: row.parameter_name ?? "",
    parameterLabel: row.parameter_label ?? "",
    upratingParameter: row.uprating_parameter ?? "",
    rounding: row.rounding ?? "",
    values: Object.fromEntries(
      years.map((year) => [year, asNumber(row[`value_${year}`])]),
    ),
    growth2026To2100Pct: asNumber(row.growth_2026_to_2100_pct),
  };
}

function parseIndexedParameterAnnualValue(
  row: Record<string, string>,
): IndexedParameterAnnualValue {
  return {
    parameterGroup: row.parameter_group ?? "",
    parameterGroupLabel: row.parameter_group_label ?? "",
    parameterName: row.parameter_name ?? "",
    parameterLabel: row.parameter_label ?? "",
    upratingParameter: row.uprating_parameter ?? "",
    rounding: row.rounding ?? "",
    year: asNumber(row.year),
    value: asNumber(row.value),
  };
}

function parseIndexingGrowth(row: Record<string, string>): IndexingGrowth {
  return {
    year: asNumber(row.year),
    indexingSource: row.indexing_source ?? "",
    growthRatePct: asNumber(row.growth_rate_pct),
  };
}

function parseCalibrationTarget(
  row: Record<string, string>,
): BaselineCalibrationTarget {
  return {
    year: asNumber(row.year),
    datasetPath: row.dataset_path ?? "",
    targetSourceName: row.target_source_name ?? "",
    targetSourceSha256: row.target_source_sha256 ?? "",
    taxAssumptionName: row.tax_assumption_name ?? "",
    constraintName: row.constraint_name ?? "",
    constraintLabel: row.constraint_label ?? "",
    constraintGroup: row.constraint_group ?? "",
    constraintClassification: row.constraint_classification ?? "",
    scoringContract: row.scoring_contract ?? "",
    source: row.source ?? "",
    target: asNumber(row.target),
    achieved: asNumber(row.achieved),
    error: asNumber(row.error),
    pctError: asNumber(row.pct_error),
    usedInYearRunnerReconciliation: asBoolean(
      row.used_in_year_runner_reconciliation,
    ),
    unit: row.unit ?? "",
  };
}

function parseCalibrationDiagnostic(
  row: Record<string, string>,
): BaselineCalibrationDiagnostic {
  return {
    year: asNumber(row.year),
    diagnosticId: row.diagnostic_id ?? "",
    diagnosticLabel: row.diagnostic_label ?? "",
    diagnosticGroup: row.diagnostic_group ?? "",
    value: asNumber(row.value),
    unit: row.unit ?? "",
    source: row.source ?? "",
    datasetPath: row.dataset_path ?? "",
    status: row.status ?? "",
  };
}

function parsePolicyParameter(
  row: Record<string, string>,
): BaselinePolicyParameter {
  return {
    year: asNumber(row.year),
    parameterName: row.parameter_name ?? "",
    parameterLabel: row.parameter_label ?? "",
    parameterGroup: row.parameter_group ?? "",
    baselineValue: row.baseline_value ?? "",
    baselineNumericValue: asNumber(row.baseline_numeric_value),
    baselineValueType: row.baseline_value_type ?? "",
    touchedByReforms: splitList(row.touched_by_reforms),
    touchedByScoringTypes: splitList(row.touched_by_scoring_types),
    policyRole: row.policy_role ?? "",
  };
}

function parseReformParameter(
  row: Record<string, string>,
): BaselineReformParameter {
  return {
    reformName: row.reform_name ?? "",
    scoringType: row.scoring_type ?? "",
    parameterName: row.parameter_name ?? "",
    parameterLabel: row.parameter_label ?? "",
    parameterGroup: row.parameter_group ?? "",
    period: row.period ?? "",
    value: row.value ?? "",
    numericValue: asNumber(row.numeric_value),
    valueType: row.value_type ?? "",
    policyRole: row.policy_role ?? "",
    affectsBaseline: asBoolean(row.affects_baseline),
  };
}

export function baselineDataHref(path: string) {
  return path.startsWith("/") && basePath ? `${basePath}${path}` : path;
}

export async function loadBaselineAssumptionsData(): Promise<BaselineAssumptionsData> {
  const [
    aggregateRows,
    indexedRows,
    indexedAnnualRows,
    growthRows,
    calibrationTargetRows,
    calibrationDiagnosticRows,
    policyParameterRows,
    reformParameterRows,
    metadata,
  ] = await Promise.all([
    parseCsvRows("/data/baseline_aggregates.csv"),
    parseCsvRows("/data/baseline_indexed_parameter_summary.csv"),
    parseCsvRows("/data/baseline_indexed_parameters.csv"),
    parseCsvRows("/data/baseline_indexing_growth.csv"),
    parseCsvRows("/data/baseline_calibration_targets.csv"),
    parseCsvRows("/data/baseline_calibration_diagnostics.csv"),
    parseCsvRows("/data/baseline_policy_parameters.csv"),
    parseCsvRows("/data/baseline_reform_parameters.csv"),
    fetchJson<BaselineAssumptionsMetadata>(
      "/data/baseline_assumptions_metadata.json",
    ),
  ]);

  return {
    aggregates: aggregateRows.map(parseAggregate).sort((a, b) => a.year - b.year),
    indexedParameters: indexedRows.map(parseIndexedParameter),
    indexedParameterValues: indexedAnnualRows
      .map(parseIndexedParameterAnnualValue)
      .sort(
        (a, b) => a.year - b.year || a.parameterName.localeCompare(b.parameterName),
      ),
    indexingGrowth: growthRows.map(parseIndexingGrowth).sort((a, b) => a.year - b.year),
    calibrationTargets: calibrationTargetRows
      .map(parseCalibrationTarget)
      .sort(
        (a, b) =>
          a.year - b.year || a.constraintName.localeCompare(b.constraintName),
      ),
    calibrationDiagnostics: calibrationDiagnosticRows
      .map(parseCalibrationDiagnostic)
      .sort(
        (a, b) =>
          a.year - b.year || a.diagnosticId.localeCompare(b.diagnosticId),
      ),
    policyParameters: policyParameterRows
      .map(parsePolicyParameter)
      .sort(
        (a, b) =>
          a.year - b.year || a.parameterName.localeCompare(b.parameterName),
      ),
    reformParameters: reformParameterRows
      .map(parseReformParameter)
      .sort(
        (a, b) =>
          a.reformName.localeCompare(b.reformName) ||
          a.parameterName.localeCompare(b.parameterName) ||
          a.period.localeCompare(b.period),
      ),
    metadata,
  };
}
