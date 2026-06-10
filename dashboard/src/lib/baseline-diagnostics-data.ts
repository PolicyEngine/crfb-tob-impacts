import Papa from "papaparse";

export interface BaselineDiagnosticsRow {
  year: number;
  [key: string]: number | null;
}

export interface DiagnosticsSeries {
  key: string;
  label: string;
  color: string;
  dashed?: boolean;
}

export interface DiagnosticsPanel {
  id: string;
  title: string;
  unit: "trillions" | "billions" | "millions" | "percent";
  calibrated: boolean;
  series: DiagnosticsSeries[];
  note?: string;
  /** Derive a ratio series on the fly: numerator / denominator. */
  ratio?: { numerator: string; denominator: string; label: string };
}

export const DIAGNOSTICS_PANELS: DiagnosticsPanel[] = [
  {
    id: "population",
    title: "Population",
    unit: "millions",
    calibrated: true,
    series: [
      { key: "population", label: "Modeled", color: "var(--chart-1)" },
      {
        key: "target_population",
        label: "TR2026 target",
        color: "var(--chart-1)",
        dashed: true,
      },
      {
        key: "population_65_plus",
        label: "Modeled 65+",
        color: "var(--chart-2)",
      },
      {
        key: "target_population_65_plus",
        label: "TR2026 65+",
        color: "var(--chart-2)",
        dashed: true,
      },
    ],
  },
  {
    id: "social-security",
    title: "Social Security benefits",
    unit: "trillions",
    calibrated: true,
    series: [
      { key: "social_security", label: "Modeled", color: "var(--chart-1)" },
      {
        key: "target_social_security",
        label: "TR2026 OASDI cost",
        color: "var(--chart-1)",
        dashed: true,
      },
    ],
  },
  {
    id: "payroll",
    title: "SSA taxable payroll",
    unit: "trillions",
    calibrated: true,
    series: [
      {
        key: "ssa_taxable_payroll",
        label: "Modeled",
        color: "var(--chart-2)",
      },
      {
        key: "target_ssa_taxable_payroll",
        label: "TR2026 target",
        color: "var(--chart-2)",
        dashed: true,
      },
    ],
  },
  {
    id: "tob",
    title: "Taxation of benefits revenue",
    unit: "billions",
    calibrated: true,
    series: [
      {
        key: "tob_revenue_oasdi",
        label: "OASDI (modeled)",
        color: "var(--chart-3)",
      },
      {
        key: "target_tob_revenue_oasdi",
        label: "OASDI (TR2026)",
        color: "var(--chart-3)",
        dashed: true,
      },
      {
        key: "tob_revenue_medicare_hi",
        label: "HI (modeled)",
        color: "var(--chart-4)",
      },
      {
        key: "target_tob_revenue_medicare_hi",
        label: "HI (TR2026)",
        color: "var(--chart-4)",
        dashed: true,
      },
    ],
  },
  {
    id: "beneficiaries",
    title: "Beneficiaries and workers",
    unit: "millions",
    calibrated: false,
    series: [
      {
        key: "ss_beneficiary_persons",
        label: "Beneficiaries (modeled)",
        color: "var(--chart-1)",
      },
      {
        key: "reference_oasdi_beneficiaries",
        label: "Beneficiaries (TR2026)",
        color: "var(--chart-1)",
        dashed: true,
      },
      {
        key: "covered_worker_persons",
        label: "Earners (modeled)",
        color: "var(--chart-2)",
      },
      {
        key: "reference_covered_workers",
        label: "Covered workers (TR2026)",
        color: "var(--chart-2)",
        dashed: true,
      },
    ],
    note: "Counts are validation holdouts, not calibration targets. The modeled earner count includes anyone with covered earnings during the year.",
  },
  {
    id: "payroll-tax",
    title: "Payroll taxes",
    unit: "trillions",
    calibrated: false,
    series: [
      {
        key: "oasdi_payroll_tax_modeled",
        label: "OASDI 12.4% (modeled)",
        color: "var(--chart-2)",
      },
      {
        key: "reference_oasdi_payroll_tax",
        label: "12.4% of payroll target",
        color: "var(--chart-2)",
        dashed: true,
      },
      {
        key: "hi_payroll_tax_modeled",
        label: "HI 2.9% (modeled)",
        color: "var(--chart-5)",
      },
      {
        key: "reference_hi_payroll_tax",
        label: "2.9% of HI payroll",
        color: "var(--chart-5)",
        dashed: true,
      },
    ],
    note: "Mechanical check: modeled statutory payroll taxes against the statutory rates applied to the payroll bases.",
  },
  {
    id: "income-tax",
    title: "Federal income tax",
    unit: "trillions",
    calibrated: false,
    series: [
      { key: "income_tax", label: "Modeled", color: "var(--chart-1)" },
    ],
    note: "Not a calibration target. The level runs above administrative collections — a known enhanced-CPS property — so the growth path, not the level, is the diagnostic.",
  },
  {
    id: "income-tax-share",
    title: "Income tax share of GDP",
    unit: "percent",
    calibrated: false,
    ratio: {
      numerator: "income_tax",
      denominator: "gdp",
      label: "Modeled / TR2026 GDP",
    },
    series: [],
    note: "Individual income taxes have averaged 8-10% of GDP historically (CBO); the modeled level sits above that range while its slope should stay gradual.",
  },
  {
    id: "agi",
    title: "Adjusted gross income share of GDP",
    unit: "percent",
    calibrated: false,
    ratio: {
      numerator: "adjusted_gross_income",
      denominator: "gdp",
      label: "AGI / TR2026 GDP",
    },
    series: [],
    note: "IRS-reported AGI has run near 65-75% of GDP.",
  },
  {
    id: "tob-share",
    title: "TOB share of benefits",
    unit: "percent",
    calibrated: true,
    ratio: {
      numerator: "tob_total",
      denominator: "social_security",
      label: "Total TOB / benefits",
    },
    series: [],
    note: "Implied average tax rate on benefits; rises as fixed nominal thresholds erode.",
  },
  {
    id: "labor-income",
    title: "Labor income",
    unit: "trillions",
    calibrated: false,
    series: [
      {
        key: "employment_income",
        label: "Employment income",
        color: "var(--chart-1)",
      },
      {
        key: "self_employment_income",
        label: "Self-employment",
        color: "var(--chart-2)",
      },
    ],
  },
  {
    id: "capital-income",
    title: "Capital and retirement income",
    unit: "trillions",
    calibrated: false,
    series: [
      {
        key: "dividends_total",
        label: "Dividends",
        color: "var(--chart-1)",
      },
      {
        key: "interest_total",
        label: "Interest",
        color: "var(--chart-2)",
      },
      {
        key: "capital_gains_total",
        label: "Capital gains",
        color: "var(--chart-3)",
      },
      {
        key: "retirement_income_total",
        label: "Pensions + IRA",
        color: "var(--chart-4)",
      },
    ],
    note: "Uncalibrated income components; gamma scales beneficiary households' values toward the TOB target while income guards pin totals from 2075.",
  },
];

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export const diagnosticsDataHref = `${basePath}/data/v2_baseline_diagnostics.csv`;

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number.parseFloat(String(value));
  return Number.isFinite(parsed) ? parsed : null;
}

export async function loadBaselineDiagnostics(): Promise<
  BaselineDiagnosticsRow[]
> {
  const response = await fetch(diagnosticsDataHref);
  if (!response.ok) {
    throw new Error(
      `Failed to fetch ${diagnosticsDataHref}: ${response.status}`,
    );
  }
  const text = await response.text();
  const parsed = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: true,
  });
  return parsed.data
    .map((raw) => {
      const row: BaselineDiagnosticsRow = {
        year: Number.parseInt(raw.year ?? "", 10),
      };
      for (const [key, value] of Object.entries(raw)) {
        if (key === "year") continue;
        row[key] = toNumber(value);
      }
      // Derived composites used by the panels.
      row.tob_total =
        (row.tob_revenue_oasdi ?? 0) + (row.tob_revenue_medicare_hi ?? 0);
      row.dividends_total =
        (row.qualified_dividend_income ?? 0) +
        (row.non_qualified_dividend_income ?? 0);
      row.interest_total =
        (row.taxable_interest_income ?? 0) +
        (row.tax_exempt_interest_income ?? 0);
      row.capital_gains_total =
        (row.long_term_capital_gains ?? 0) +
        (row.short_term_capital_gains ?? 0);
      row.retirement_income_total =
        (row.taxable_pension_income ?? 0) +
        (row.taxable_ira_distributions ?? 0);
      row.oasdi_payroll_tax_modeled =
        (row.employee_social_security_tax ?? 0) * 2 +
        (row.self_employment_social_security_tax ?? 0);
      row.hi_payroll_tax_modeled =
        (row.employee_medicare_tax ?? 0) * 2 +
        (row.self_employment_medicare_tax ?? 0);
      return row;
    })
    .filter((row) => Number.isFinite(row.year))
    .sort((a, b) => a.year - b.year);
}
