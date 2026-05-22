"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Database,
  Download,
  LoaderCircle,
  SlidersHorizontal,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  baselineDataHref,
  loadBaselineAssumptionsData,
  type BaselineAggregate,
  type BaselineAssumptionsData,
  type BaselineCalibrationTarget,
  type BaselinePolicyParameter,
  type IndexedParameterSummary,
} from "@/lib/baseline-assumptions-data";
import { useElementSize } from "@/lib/use-element-size";

const SPOTLIGHT_YEARS = [2026, 2035, 2050, 2075, 2100];
const PARAMETER_YEARS = [2026, 2035, 2050, 2075, 2100];
const CALIBRATION_SERIES = [
  {
    key: "ss_total",
    name: "SS benefits",
    color: "var(--chart-1)",
  },
  {
    key: "payroll_total",
    name: "OASDI payroll",
    color: "var(--chart-2)",
  },
  {
    key: "oasdi_tob",
    name: "OASDI TOB",
    color: "var(--chart-3)",
  },
  {
    key: "hi_tob",
    name: "HI TOB",
    color: "var(--chart-4)",
  },
] as const;

const THRESHOLD_SERIES = [
  {
    key: "standardDeductionSingle",
    name: "Standard deduction",
    parameterName: "gov.irs.deductions.standard.amount.SINGLE",
    color: "var(--chart-1)",
  },
  {
    key: "ordinaryBracket1Single",
    name: "Ordinary bracket 1",
    parameterName: "gov.irs.income.bracket.thresholds.1.SINGLE",
    color: "var(--chart-2)",
  },
  {
    key: "ordinaryBracket6Single",
    name: "Ordinary bracket 6",
    parameterName: "gov.irs.income.bracket.thresholds.6.SINGLE",
    color: "var(--chart-3)",
  },
  {
    key: "amtExemptionSingle",
    name: "AMT exemption",
    parameterName: "gov.irs.income.amt.exemption.amount.SINGLE",
    color: "var(--chart-4)",
  },
] as const;

type BaselineChartRow = {
  year: number;
  total: number;
  oasdi: number;
  hi: number;
};

type ThresholdChartRow = {
  year: number;
  [key: string]: number;
};

type CalibrationErrorChartRow = {
  year: number;
  [key: string]: number;
};

type ReformTouchedParameterRow = {
  parameterName: string;
  parameterLabel: string;
  parameterGroup: string;
  policyRole: string;
  touchedByReforms: string[];
  touchedByScoringTypes: string[];
  valueType: string;
  values: Record<number, number>;
};

type ThresholdSeriesKey = (typeof THRESHOLD_SERIES)[number]["key"];

function formatBillions(value: number) {
  const rounded = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1);
  return `${value >= 0 ? "$" : "-$"}${Math.abs(Number(rounded)).toLocaleString()}B`;
}

function formatCurrency(value: number) {
  const absoluteValue = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (absoluteValue >= 1_000_000) {
    const millions = absoluteValue / 1_000_000;
    const formatted =
      millions >= 10
        ? millions.toFixed(1)
        : millions.toFixed(2);
    return `${sign}$${formatted.replace(/\.0+$/, "")}M`;
  }
  return `${sign}$${Math.round(absoluteValue).toLocaleString()}`;
}

function formatPercent(value: number, decimals = 2) {
  return `${value.toFixed(decimals)}%`;
}

function formatPlainNumber(value: number) {
  const absoluteValue = Math.abs(value);
  if (absoluteValue === 0) return "0";
  if (absoluteValue < 1) return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  if (absoluteValue < 100) return value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatParameterValue(value: number, valueType: string) {
  if (valueType === "missing") return "n/a";
  if (valueType === "boolean") return value >= 0.5 ? "true" : "false";
  if (Math.abs(value) >= 1_000) return formatCurrency(value);
  return formatPlainNumber(value);
}

function formatThousands(value: number) {
  const rounded = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1);
  return `${value >= 0 ? "$" : "-$"}${Math.abs(Number(rounded)).toLocaleString()}K`;
}

function formatTargetValue(target: BaselineCalibrationTarget, value: number) {
  if (target.unit.includes("billions")) return formatBillions(value);
  if (target.unit === "percent") return formatPercent(value);
  return formatPlainNumber(value);
}

function formatGeneratedAt(value?: string) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "n/a";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatSha(value?: string) {
  if (!value) return "n/a";
  return `${value.slice(0, 12)}…`;
}

function DataLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={baselineDataHref(href)}
      className="inline-flex items-center gap-2 rounded-full border border-[var(--pe-color-border-medium)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--pe-color-text-primary)] transition hover:border-[var(--pe-color-primary-300)] hover:text-[var(--pe-color-primary-700)]"
    >
      <Download className="h-3.5 w-3.5" />
      {label}
    </a>
  );
}

function AssumptionMetric({
  label,
  value,
  caption,
}: {
  label: string;
  value: string;
  caption: string;
}) {
  return (
    <div className="border-l-[3px] border-l-[var(--pe-color-primary-500)] bg-white px-5 py-4 shadow-[0_12px_28px_rgba(16,24,40,0.05)]">
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
        {label}
      </p>
      <p className="mt-2 text-[27px] font-bold leading-none tracking-[-0.02em] text-[var(--pe-color-text-title)]">
        {value}
      </p>
      <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
        {caption}
      </p>
    </div>
  );
}

function aggregateSpotlightRows(aggregates: BaselineAggregate[]) {
  return SPOTLIGHT_YEARS.map((year) =>
    aggregates.find((row) => row.year === year),
  ).filter(Boolean) as BaselineAggregate[];
}

function CalibratedBaselineChart({
  chartData,
}: {
  chartData: BaselineChartRow[];
}) {
  const { ref, width, height } = useElementSize<HTMLDivElement>();

  return (
    <div ref={ref} className="mt-4 h-[22rem]">
      {width > 0 && height > 0 ? (
        <AreaChart
          width={width}
          height={height}
          data={chartData}
          margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="baselineOasdiFill" x1="0" x2="0" y1="0" y2="1">
              <stop
                offset="0%"
                stopColor="var(--pe-color-primary-500)"
                stopOpacity={0.25}
              />
              <stop
                offset="100%"
                stopColor="var(--pe-color-primary-500)"
                stopOpacity={0}
              />
            </linearGradient>
            <linearGradient id="baselineHiFill" x1="0" x2="0" y1="0" y2="1">
              <stop
                offset="0%"
                stopColor="var(--pe-color-gray-500)"
                stopOpacity={0.22}
              />
              <stop
                offset="100%"
                stopColor="var(--pe-color-gray-500)"
                stopOpacity={0}
              />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="var(--pe-color-border-light)"
            strokeDasharray="3 5"
            vertical={false}
          />
          <XAxis
            dataKey="year"
            type="number"
            niceTicks="snap125"
            domain={["auto", "auto"]}
            tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            niceTicks="snap125"
            domain={["auto", "auto"]}
            tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => formatBillions(value).replace("B", "")}
          />
          <Tooltip
            separator=": "
            contentStyle={{
              borderRadius: "12px",
              border: "1px solid var(--pe-color-border-light)",
              boxShadow: "0 18px 48px rgba(16, 24, 40, 0.12)",
              fontSize: "13px",
            }}
            formatter={(value, name) => [
              formatBillions(Number(value)),
              name === "oasdi" ? "OASDI" : name === "hi" ? "HI" : "Total",
            ]}
          />
          <Legend />
          <Area
            type="monotone"
            dataKey="oasdi"
            name="OASDI"
            stroke="var(--pe-color-primary-500)"
            fill="url(#baselineOasdiFill)"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="hi"
            name="HI"
            stroke="var(--pe-color-gray-500)"
            fill="url(#baselineHiFill)"
            strokeWidth={2}
          />
          <Line
            type="monotone"
            dataKey="total"
            name="Total"
            stroke="var(--pe-color-text-primary)"
            strokeWidth={2.5}
            dot={false}
          />
        </AreaChart>
      ) : null}
    </div>
  );
}

function TaxThresholdChart({ chartData }: { chartData: ThresholdChartRow[] }) {
  const { ref, width, height } = useElementSize<HTMLDivElement>();

  return (
    <div ref={ref} className="mt-4 h-[18rem]">
      {width > 0 && height > 0 ? (
        <LineChart
          width={width}
          height={height}
          data={chartData}
          margin={{ top: 8, right: 18, bottom: 0, left: 0 }}
        >
          <CartesianGrid
            stroke="var(--pe-color-border-light)"
            strokeDasharray="3 5"
            vertical={false}
          />
          <XAxis
            dataKey="year"
            type="number"
            niceTicks="snap125"
            domain={["auto", "auto"]}
            tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            niceTicks="snap125"
            domain={["auto", "auto"]}
            tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => formatThousands(value)}
          />
          <Tooltip
            separator=": "
            contentStyle={{
              borderRadius: "12px",
              border: "1px solid var(--pe-color-border-light)",
              boxShadow: "0 18px 48px rgba(16, 24, 40, 0.12)",
              fontSize: "13px",
            }}
            formatter={(value, name) => [
              formatThousands(Number(value)),
              THRESHOLD_SERIES.find((series) => series.key === name)?.name ?? name,
            ]}
          />
          <Legend />
          <ReferenceLine
            x={2035}
            stroke="var(--pe-color-border-strong)"
            strokeDasharray="4 4"
            label={{
              value: "Wage indexing",
              fill: "var(--pe-color-text-tertiary)",
              fontSize: 11,
              position: "insideTop",
            }}
          />
          {THRESHOLD_SERIES.map((series) => (
            <Line
              key={series.key}
              type="monotone"
              dataKey={series.key}
              name={series.name}
              stroke={series.color}
              strokeWidth={2.25}
              dot={false}
            />
          ))}
        </LineChart>
      ) : null}
    </div>
  );
}

function CalibrationErrorChart({
  chartData,
}: {
  chartData: CalibrationErrorChartRow[];
}) {
  const { ref, width, height } = useElementSize<HTMLDivElement>();

  return (
    <div ref={ref} className="mt-4 h-[18rem]">
      {width > 0 && height > 0 ? (
        <LineChart
          width={width}
          height={height}
          data={chartData}
          margin={{ top: 8, right: 18, bottom: 0, left: 0 }}
        >
          <CartesianGrid
            stroke="var(--pe-color-border-light)"
            strokeDasharray="3 5"
            vertical={false}
          />
          <XAxis
            dataKey="year"
            type="number"
            niceTicks="snap125"
            domain={["auto", "auto"]}
            tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            niceTicks="snap125"
            domain={["auto", "auto"]}
            tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => `${value.toFixed(2)}%`}
          />
          <Tooltip
            separator=": "
            contentStyle={{
              borderRadius: "12px",
              border: "1px solid var(--pe-color-border-light)",
              boxShadow: "0 18px 48px rgba(16, 24, 40, 0.12)",
              fontSize: "13px",
            }}
            formatter={(value, name) => [
              formatPercent(Number(value), 4),
              CALIBRATION_SERIES.find((series) => series.key === name)?.name ?? name,
            ]}
          />
          <Legend />
          {CALIBRATION_SERIES.map((series) => (
            <Line
              key={series.key}
              type="monotone"
              dataKey={series.key}
              name={series.name}
              stroke={series.color}
              strokeWidth={2.25}
              dot={{ r: 2 }}
              connectNulls
            />
          ))}
        </LineChart>
      ) : null}
    </div>
  );
}

function IndexedParameterTable({
  parameters,
}: {
  parameters: IndexedParameterSummary[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-[62rem] text-sm">
        <thead>
          <tr className="border-b border-[var(--pe-color-border-light)] text-[11px] uppercase tracking-[0.12em] text-[var(--pe-color-text-tertiary)]">
            <th className="px-4 py-2 text-left font-medium">Group</th>
            <th className="px-4 py-2 text-left font-medium">Parameter</th>
            {PARAMETER_YEARS.map((year) => (
              <th key={year} className="px-4 py-2 text-right font-medium">
                {year}
              </th>
            ))}
            <th className="px-4 py-2 text-right font-medium">2026-2100</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--pe-color-border-light)]">
          {parameters.map((parameter) => (
            <tr key={parameter.parameterName} className="align-top">
              <td className="max-w-[13rem] px-4 py-2.5 text-[var(--pe-color-text-secondary)]">
                {parameter.parameterGroupLabel}
              </td>
              <td className="max-w-[18rem] px-4 py-2.5">
                <p className="font-medium text-[var(--pe-color-text-primary)]">
                  {parameter.parameterLabel}
                </p>
                <p className="mt-1 break-all text-xs leading-5 text-[var(--pe-color-text-tertiary)]">
                  {parameter.parameterName}
                </p>
              </td>
              {PARAMETER_YEARS.map((year) => (
                <td
                  key={year}
                  className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-text-primary)]"
                >
                  {formatCurrency(parameter.values[year])}
                </td>
              ))}
              <td className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                {formatPercent(parameter.growth2026To2100Pct, 1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function buildReformTouchedParameterRows(
  parameters: BaselinePolicyParameter[],
): ReformTouchedParameterRow[] {
  const rows = new Map<string, ReformTouchedParameterRow>();
  for (const parameter of parameters) {
    if (!PARAMETER_YEARS.includes(parameter.year)) continue;
    const existing = rows.get(parameter.parameterName) ?? {
      parameterName: parameter.parameterName,
      parameterLabel: parameter.parameterLabel,
      parameterGroup: parameter.parameterGroup,
      policyRole: parameter.policyRole,
      touchedByReforms: parameter.touchedByReforms,
      touchedByScoringTypes: parameter.touchedByScoringTypes,
      valueType: parameter.baselineValueType,
      values: {},
    };
    existing.values[parameter.year] = parameter.baselineNumericValue;
    rows.set(parameter.parameterName, existing);
  }
  return [...rows.values()].sort(
    (a, b) =>
      a.parameterGroup.localeCompare(b.parameterGroup) ||
      a.parameterName.localeCompare(b.parameterName),
  );
}

function ReformTouchedParameterTable({
  rows,
}: {
  rows: ReformTouchedParameterRow[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-[68rem] text-sm">
        <thead>
          <tr className="border-b border-[var(--pe-color-border-light)] text-[11px] uppercase tracking-[0.12em] text-[var(--pe-color-text-tertiary)]">
            <th className="px-4 py-2 text-left font-medium">Group</th>
            <th className="px-4 py-2 text-left font-medium">Parameter</th>
            {PARAMETER_YEARS.map((year) => (
              <th key={year} className="px-4 py-2 text-right font-medium">
                {year}
              </th>
            ))}
            <th className="px-4 py-2 text-left font-medium">Touched by</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--pe-color-border-light)]">
          {rows.map((row) => (
            <tr key={row.parameterName} className="align-top">
              <td className="max-w-[12rem] px-4 py-2.5 text-[var(--pe-color-text-secondary)]">
                {row.parameterGroup}
              </td>
              <td className="max-w-[18rem] px-4 py-2.5">
                <p className="font-medium text-[var(--pe-color-text-primary)]">
                  {row.parameterLabel}
                </p>
                <p className="mt-1 break-all text-xs leading-5 text-[var(--pe-color-text-tertiary)]">
                  {row.parameterName}
                </p>
              </td>
              {PARAMETER_YEARS.map((year) => (
                <td
                  key={year}
                  className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-text-primary)]"
                >
                  {formatParameterValue(row.values[year] ?? 0, row.valueType)}
                </td>
              ))}
              <td className="max-w-[15rem] px-4 py-2.5 text-[var(--pe-color-text-secondary)]">
                <p>{row.touchedByReforms.join(", ")}</p>
                <p className="mt-1 text-xs text-[var(--pe-color-text-tertiary)]">
                  {row.touchedByScoringTypes.join(", ")}
                </p>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BaselineAssumptionsSection() {
  const [data, setData] = useState<BaselineAssumptionsData | null>(null);
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loadBaselineAssumptionsData()
      .then((result) => {
        if (!active) return;
        setData(result);
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Failed to load baseline assumptions.",
        );
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const groupOptions = useMemo(() => {
    if (!data) return [];
    const labels = new Map<string, string>();
    for (const parameter of data.indexedParameters) {
      labels.set(parameter.parameterGroup, parameter.parameterGroupLabel);
    }
    return [...labels.entries()];
  }, [data]);

  const filteredParameters = useMemo(() => {
    if (!data) return [];
    if (selectedGroup === "all") return data.indexedParameters;
    return data.indexedParameters.filter(
      (parameter) => parameter.parameterGroup === selectedGroup,
    );
  }, [data, selectedGroup]);

  const thresholdChartData = useMemo(() => {
    if (!data) return [];
    const rows = new Map<number, ThresholdChartRow>();
    const selectedParameterNames = new Map<string, ThresholdSeriesKey>(
      THRESHOLD_SERIES.map((series) => [series.parameterName, series.key]),
    );

    for (const parameter of data.indexedParameterValues) {
      const key = selectedParameterNames.get(parameter.parameterName);
      if (!key) continue;
      const row = rows.get(parameter.year) ?? { year: parameter.year };
      row[key] = parameter.value / 1_000;
      rows.set(parameter.year, row);
    }

    return [...rows.values()].sort((a, b) => a.year - b.year);
  }, [data]);

  const calibrationErrorChartData = useMemo(() => {
    if (!data) return [];
    const selected = new Set<string>(CALIBRATION_SERIES.map((series) => series.key));
    const rows = new Map<number, CalibrationErrorChartRow>();

    for (const target of data.calibrationTargets) {
      if (!selected.has(target.constraintName)) continue;
      const row = rows.get(target.year) ?? { year: target.year };
      row[target.constraintName] = Math.abs(target.pctError);
      rows.set(target.year, row);
    }

    return [...rows.values()].sort((a, b) => a.year - b.year);
  }, [data]);

  const calibrationTargetRows = useMemo(() => {
    if (!data) return [];
    const selected = new Set<string>(CALIBRATION_SERIES.map((series) => series.key));
    return data.calibrationTargets.filter(
      (target) =>
        selected.has(target.constraintName) &&
        (SPOTLIGHT_YEARS.includes(target.year) ||
          target.usedInYearRunnerReconciliation),
    );
  }, [data]);

  const reformTouchedParameterRows = useMemo(() => {
    if (!data) return [];
    return buildReformTouchedParameterRows(data.policyParameters);
  }, [data]);

  if (loading) {
    return (
      <section className="flex min-h-[24rem] items-center justify-center rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
        <div className="flex items-center gap-3 text-[var(--pe-color-text-secondary)]">
          <LoaderCircle className="h-5 w-5 animate-spin" />
          <span>Loading baseline model data…</span>
        </div>
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-error)] bg-white px-5 py-6 text-[var(--pe-color-error)]">
        {error ?? "Baseline model data are unavailable."}
      </section>
    );
  }

  const aggregateRows = aggregateSpotlightRows(data.aggregates);
  const baseline2026 = data.aggregates.find((row) => row.year === 2026);
  const baseline2100 = data.aggregates.find((row) => row.year === 2100);
  const growthSpotlight = data.indexingGrowth.filter((row) =>
    [2035, 2036, 2050, 2075, 2100].includes(row.year),
  );
  const metadata = data.metadata;
  const taxAssumption = metadata.tax_assumption;
  const runtimeCaption = [
    metadata.policyengine_us_version
      ? `policyengine-us ${metadata.policyengine_us_version}`
      : null,
    metadata.policyengine_core_version
      ? `core ${metadata.policyengine_core_version}`
      : null,
  ]
    .filter(Boolean)
    .join(" / ");

  const chartData = data.aggregates.map((row) => ({
    year: row.year,
    total: row.tobTotal,
    oasdi: row.tobOasdi,
    hi: row.tobHi,
  }));

  return (
    <>
      <section className="border-t border-[var(--pe-color-border-light)] pt-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--pe-color-primary-700)]">
              Audit surface
            </p>
            <h3 className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
              Baseline model outputs and assumptions
            </h3>
            <p className="mt-2 max-w-3xl text-base leading-7 text-[var(--pe-color-text-secondary)]">
              Direct microsimulation aggregates, Trustees-following reference
              targets, and the tax parameters that are indexed in the long-run
              baseline.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <DataLink href="/data/baseline_aggregates.csv" label="Aggregates CSV" />
            <DataLink
              href="/data/baseline_indexed_parameters.csv"
              label="Full parameter CSV"
            />
            <DataLink
              href="/data/baseline_indexed_parameter_summary.csv"
              label="Parameter summary"
            />
            <DataLink
              href="/data/baseline_calibration_targets.csv"
              label="Targets CSV"
            />
            <DataLink
              href="/data/baseline_policy_parameters.csv"
              label="Policy parameters"
            />
            <DataLink
              href="/data/baseline_assumptions_metadata.json"
              label="Metadata JSON"
            />
            <DataLink
              href="/data/post_obbba_tob_baseline_manifest.json"
              label="Baseline manifest"
            />
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <AssumptionMetric
          label="2026 TOB baseline"
          value={baseline2026 ? formatBillions(baseline2026.tobTotal) : "n/a"}
          caption="Post-OBBBA OASDI plus HI benefit-tax revenue"
        />
        <AssumptionMetric
          label="2100 TOB baseline"
          value={baseline2100 ? formatBillions(baseline2100.tobTotal) : "n/a"}
          caption="Nominal annual calibrated baseline"
        />
        <AssumptionMetric
          label="Indexed parameters"
          value={String(data.indexedParameters.length)}
          caption="Core tax thresholds in the baseline path"
        />
        <AssumptionMetric
          label="Calibration targets"
          value={String(data.calibrationTargets.length)}
          caption="Target and achieved rows exposed for audit"
        />
        <AssumptionMetric
          label="Assumption"
          value={taxAssumption?.name ?? "n/a"}
          caption={`Generated ${formatGeneratedAt(metadata.generated_at)}`}
        />
        <AssumptionMetric
          label="Runtime"
          value={
            metadata.policyengine_version
              ? `policyengine.py ${metadata.policyengine_version}`
              : "n/a"
          }
          caption={runtimeCaption || "Installed package stack"}
        />
      </section>

      <section className="grid gap-6 2xl:grid-cols-[minmax(0,0.95fr)_minmax(32rem,1.05fr)]">
        <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h4 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
              Calibration target errors
            </h4>
            <p className="text-xs text-[var(--pe-color-text-tertiary)]">
              Absolute percent error
            </p>
          </div>
          <CalibrationErrorChart chartData={calibrationErrorChartData} />
        </div>

        <div className="overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
          <div className="border-b border-[var(--pe-color-border-light)] px-5 py-3">
            <h4 className="text-sm font-semibold text-[var(--pe-color-text-title)]">
              Calibration target checkpoints
            </h4>
          </div>
          <div className="max-h-[22rem] overflow-auto">
            <table className="min-w-[58rem] text-sm">
              <thead>
                <tr className="sticky top-0 border-b border-[var(--pe-color-border-light)] bg-white text-[11px] uppercase tracking-[0.12em] text-[var(--pe-color-text-tertiary)]">
                  <th className="px-4 py-2 text-left font-medium">Year</th>
                  <th className="px-4 py-2 text-left font-medium">Target</th>
                  <th className="px-4 py-2 text-right font-medium">Expected</th>
                  <th className="px-4 py-2 text-right font-medium">Achieved</th>
                  <th className="px-4 py-2 text-right font-medium">Error</th>
                  <th className="px-4 py-2 text-left font-medium">Contract</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--pe-color-border-light)]">
                {calibrationTargetRows.map((target) => (
                  <tr key={`${target.year}-${target.constraintName}`}>
                    <td className="px-4 py-2.5 font-medium">{target.year}</td>
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-[var(--pe-color-text-primary)]">
                        {target.constraintLabel}
                      </p>
                      <p className="mt-1 text-xs text-[var(--pe-color-text-tertiary)]">
                        {target.constraintClassification || "published"}
                      </p>
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatTargetValue(target, target.target)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatTargetValue(target, target.achieved)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatPercent(target.pctError, 4)}
                    </td>
                    <td className="max-w-[18rem] px-4 py-2.5 text-[var(--pe-color-text-secondary)]">
                      {target.scoringContract || target.source}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section>
        <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h4 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
                Indexed income-tax thresholds
              </h4>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--pe-color-text-secondary)]">
                Single-filer thresholds used by the baseline path. The vertical
                marker is the shift from default IRS uprating to Trustees wage
                indexing.
              </p>
            </div>
            <div className="rounded-full bg-[var(--pe-color-bg-secondary)] px-3 py-1 text-xs font-medium text-[var(--pe-color-text-secondary)]">
              Thousands of dollars
            </div>
          </div>
          <TaxThresholdChart chartData={thresholdChartData} />
        </div>
      </section>

      <section className="grid gap-6 2xl:grid-cols-[minmax(0,1.15fr)_minmax(28rem,0.85fr)]">
        <div className="min-w-0 rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h4 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
              Post-OBBBA calibrated TOB baseline
            </h4>
            <p className="text-xs text-[var(--pe-color-text-tertiary)]">
              Billions of nominal dollars
            </p>
          </div>
          <CalibratedBaselineChart chartData={chartData} />
        </div>

        <div className="overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
          <div className="border-b border-[var(--pe-color-border-light)] px-5 py-3">
            <h4 className="text-sm font-semibold text-[var(--pe-color-text-title)]">
              Baseline aggregate checkpoints
            </h4>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-[76rem] text-sm">
              <thead>
                <tr className="border-b border-[var(--pe-color-border-light)] text-[11px] uppercase tracking-[0.12em] text-[var(--pe-color-text-tertiary)]">
                  <th className="px-4 py-2 text-left font-medium">Year</th>
                  <th className="px-4 py-2 text-right font-medium">Income tax</th>
                  <th className="px-4 py-2 text-right font-medium">Income tax / GDP</th>
                  <th className="px-4 py-2 text-right font-medium">TOB total</th>
                  <th className="px-4 py-2 text-right font-medium">vs current law</th>
                  <th className="px-4 py-2 text-right font-medium">OASDI</th>
                  <th className="px-4 py-2 text-right font-medium">HI</th>
                  <th className="px-4 py-2 text-right font-medium">TOB / payroll</th>
                  <th className="px-4 py-2 text-right font-medium">OASDI payroll</th>
                  <th className="px-4 py-2 text-right font-medium">HI payroll</th>
                  <th className="px-4 py-2 text-right font-medium">GDP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--pe-color-border-light)]">
                {aggregateRows.map((row) => (
                  <tr key={row.year}>
                    <td className="px-4 py-2.5 font-medium">{row.year}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatBillions(row.federalIncomeTax)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatPercent(row.federalIncomeTaxPctGdp)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-semibold tabular-nums">
                      {formatBillions(row.tobTotal)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                      {formatBillions(row.postObbbaTobDelta)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-primary-700)]">
                      {formatBillions(row.tobOasdi)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                      {formatBillions(row.tobHi)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatPercent(row.tobTotalPctOasdiPayroll)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                      {formatBillions(row.oasdiTaxablePayroll)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                      {formatBillions(row.hiTaxablePayroll)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                      {formatBillions(row.gdp)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-5">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-[var(--pe-color-primary-700)]" />
            <h4 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
              Calibration contract
            </h4>
          </div>
          <dl className="mt-4 divide-y divide-[var(--pe-color-border-light)] text-sm">
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">Target</dt>
              <dd className="text-[var(--pe-color-text-primary)]">
                {baseline2026?.calibrationTarget ?? "n/a"}
              </dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">TOB source</dt>
              <dd className="text-[var(--pe-color-text-primary)]">
                {metadata.source_post_obbba_tob_baseline ?? "n/a"}
              </dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">
                Scenario
              </dt>
              <dd className="break-all text-[var(--pe-color-text-primary)]">
                {metadata.scenario_id ?? baseline2026?.scenarioId ?? "n/a"}
              </dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">
                Baseline hash
              </dt>
              <dd
                className="break-all font-mono text-xs text-[var(--pe-color-text-primary)]"
                title={
                  metadata.post_obbba_tob_baseline_sha256 ??
                  baseline2026?.baselineSha256
                }
              >
                {formatSha(
                  metadata.post_obbba_tob_baseline_sha256 ??
                    baseline2026?.baselineSha256,
                )}
              </dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">
                Manifest
              </dt>
              <dd className="break-all text-[var(--pe-color-text-primary)]">
                {metadata.source_post_obbba_tob_baseline_manifest ??
                  baseline2026?.baselineManifest ??
                  "n/a"}
              </dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">Quality</dt>
              <dd className="text-[var(--pe-color-text-primary)]">
                {baseline2026?.calibrationQuality ?? "n/a"}
              </dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">HI method</dt>
              <dd className="text-[var(--pe-color-text-primary)]">
                {baseline2026?.hiMethod ?? "n/a"}
              </dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">
                Tax threshold rule
              </dt>
              <dd className="text-[var(--pe-color-text-primary)]">
                {taxAssumption?.description ?? "n/a"}
              </dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-medium text-[var(--pe-color-text-secondary)]">
                Tax threshold source
              </dt>
              <dd className="text-[var(--pe-color-text-primary)]">
                {taxAssumption?.source ?? "n/a"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-5">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-[var(--pe-color-primary-700)]" />
            <h4 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
              Indexing path
            </h4>
          </div>
          <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
            Core tax thresholds follow default IRS uprating through 2034 and
            Trustees average-wage growth from 2035 forward.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--pe-color-border-light)] text-[11px] uppercase tracking-[0.12em] text-[var(--pe-color-text-tertiary)]">
                  <th className="px-4 py-2 text-left font-medium">Year</th>
                  <th className="px-4 py-2 text-left font-medium">Index source</th>
                  <th className="px-4 py-2 text-right font-medium">Growth</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--pe-color-border-light)]">
                {growthSpotlight.map((row) => (
                  <tr key={row.year}>
                    <td className="px-4 py-2.5 font-medium">{row.year}</td>
                    <td className="px-4 py-2.5 text-[var(--pe-color-text-secondary)]">
                      {row.indexingSource}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatPercent(row.growthRatePct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
        <div className="flex flex-col gap-3 border-b border-[var(--pe-color-border-light)] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h4 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
              Indexed policy parameters
            </h4>
            <p className="mt-1 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
              Summary checkpoints for every indexed parameter. The full CSV has
              annual values for 2026-2100.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-[var(--pe-color-text-secondary)]">
            Group
            <select
              value={selectedGroup}
              onChange={(event) => setSelectedGroup(event.target.value)}
              className="rounded-full border border-[var(--pe-color-border-medium)] bg-white px-3 py-1.5 text-sm font-medium text-[var(--pe-color-text-primary)] outline-none transition focus:border-[var(--pe-color-primary-400)]"
            >
              <option value="all">All groups</option>
              {groupOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <IndexedParameterTable parameters={filteredParameters} />
      </section>

      <section className="overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
        <div className="flex flex-col gap-3 border-b border-[var(--pe-color-border-light)] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h4 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
              Reform-touched baseline parameters
            </h4>
            <p className="mt-1 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
              Baseline values for every parameter modified by the static or
              labor-supply-response reform dictionaries.
            </p>
          </div>
          <DataLink
            href="/data/baseline_reform_parameters.csv"
            label="Reform parameter CSV"
          />
        </div>
        <ReformTouchedParameterTable rows={reformTouchedParameterRows} />
      </section>
    </>
  );
}
