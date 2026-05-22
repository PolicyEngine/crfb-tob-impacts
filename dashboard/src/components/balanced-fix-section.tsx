"use client";

import { CheckCircle2, Database, Download, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  NameType,
  ValueType,
} from "recharts/types/component/DefaultTooltipContent";

import {
  balancedFixDataHref,
  loadBalancedFixData,
  type BalancedFixData,
  type BalancedFixRow,
} from "@/lib/balanced-fix-data";
import { useElementSize } from "@/lib/use-element-size";

const SPOTLIGHT_YEARS = [2035, 2050, 2075, 2100];

function formatMillions(value: number) {
  const rounded = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2);
  return `${value >= 0 ? "$" : "-$"}${Math.abs(Number(rounded)).toLocaleString()}M`;
}

function formatPercent(value: number, decimals = 2) {
  return `${value.toFixed(decimals)}%`;
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

function shortSha(value: string) {
  return value ? `${value.slice(0, 10)}…` : "n/a";
}

function dataDownloadHref(path: string) {
  return balancedFixDataHref(`/data/${path}`);
}

function DataLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={dataDownloadHref(href)}
      className="inline-flex items-center gap-2 rounded-full border border-[var(--pe-color-border-medium)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--pe-color-text-primary)] transition hover:border-[var(--pe-color-primary-300)] hover:text-[var(--pe-color-primary-700)]"
    >
      <Download className="h-3.5 w-3.5" />
      {label}
    </a>
  );
}

function MetricTile({
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

function IntegrityFlag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--pe-color-primary-50)] px-3 py-1.5 text-xs font-medium text-[var(--pe-color-primary-800)]">
      <CheckCircle2 className="h-3.5 w-3.5" />
      {children}
    </span>
  );
}

function tooltipLabel(
  value: ValueType | undefined,
  name: NameType | undefined,
): [string, string] {
  const numericValue =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number.parseFloat(value)
        : NaN;
  const formattedValue = Number.isFinite(numericValue)
    ? formatPercent(numericValue)
    : "n/a";
  const label =
    name === "benefitCutPct"
      ? "Benefit cut"
      : name === "combinedSsRatePct"
        ? "Combined OASDI rate"
        : "Combined HI rate";
  return [formattedValue, label];
}

function BalancedFixChart({ rows }: { rows: BalancedFixRow[] }) {
  const { ref, width, height } = useElementSize<HTMLDivElement>();
  const chartData = rows.map((row) => ({
    year: row.year,
    benefitCutPct: row.benefitCutPct,
    combinedSsRatePct: row.combinedSsRatePct,
    combinedHiRatePct: row.combinedHiRatePct,
  }));

  return (
    <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
          Annual balanced-fix settings
        </h3>
        <p className="text-xs text-[var(--pe-color-text-tertiary)]">
          Exact modeled years, no interpolation
        </p>
      </div>

      <div ref={ref} className="mt-4 h-[23rem]">
        {width > 0 && height > 0 ? (
          <LineChart
            width={width}
            height={height}
            data={chartData}
            margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              stroke="var(--pe-color-border-light)"
              strokeDasharray="3 5"
              vertical={false}
            />
            <XAxis
              dataKey="year"
              tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="number"
              niceTicks="snap125"
              domain={["auto", "auto"]}
              tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => `${value.toFixed(0)}%`}
            />
            <ReferenceLine
              y={12.4}
              stroke="var(--pe-color-border-medium)"
              strokeDasharray="4 4"
            />
            <Tooltip
              separator=": "
              contentStyle={{
                borderRadius: "12px",
                border: "1px solid var(--pe-color-border-light)",
                boxShadow: "0 18px 48px rgba(16, 24, 40, 0.12)",
                fontSize: "13px",
              }}
              formatter={(value, name) => tooltipLabel(value, name)}
            />
            <Legend verticalAlign="top" height={32} />
            <Line
              name="Benefit cut"
              type="monotone"
              dataKey="benefitCutPct"
              stroke="var(--chart-1)"
              strokeWidth={2.5}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
            <Line
              name="Combined OASDI rate"
              type="monotone"
              dataKey="combinedSsRatePct"
              stroke="var(--chart-2)"
              strokeWidth={2.5}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
            <Line
              name="Combined HI rate"
              type="monotone"
              dataKey="combinedHiRatePct"
              stroke="var(--chart-5)"
              strokeWidth={2.5}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        ) : null}
      </div>
    </div>
  );
}

function SpotlightTable({ rows }: { rows: BalancedFixRow[] }) {
  const spotlightRows = rows.filter((row) => SPOTLIGHT_YEARS.includes(row.year));

  return (
    <div className="overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
      <div className="border-b border-[var(--pe-color-border-light)] px-5 py-3">
        <h4 className="text-sm font-semibold text-[var(--pe-color-text-title)]">
          Selected years
        </h4>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-[var(--pe-color-text-secondary)]">
            <tr className="border-b border-[var(--pe-color-border-light)]">
              <th className="px-5 py-2 text-left text-xs font-medium uppercase tracking-wide">
                Year
              </th>
              <th className="px-5 py-2 text-right text-xs font-medium uppercase tracking-wide">
                Benefit cut
              </th>
              <th className="px-5 py-2 text-right text-xs font-medium uppercase tracking-wide">
                OASDI rate
              </th>
              <th className="px-5 py-2 text-right text-xs font-medium uppercase tracking-wide">
                HI rate
              </th>
              <th className="px-5 py-2 text-right text-xs font-medium uppercase tracking-wide">
                Residual gap
              </th>
              <th className="px-5 py-2 text-right text-xs font-medium uppercase tracking-wide">
                H5 hash
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--pe-color-border-light)]">
            {spotlightRows.map((row) => (
              <tr key={row.year}>
                <td className="px-5 py-2.5 font-medium text-[var(--pe-color-text-primary)]">
                  {row.year}
                </td>
                <td className="px-5 py-2.5 text-right tabular-nums text-[var(--pe-color-text-primary)]">
                  {formatPercent(row.benefitCutPct)}
                </td>
                <td className="px-5 py-2.5 text-right tabular-nums text-[var(--pe-color-primary-700)]">
                  {formatPercent(row.combinedSsRatePct)}
                </td>
                <td className="px-5 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                  {formatPercent(row.combinedHiRatePct)}
                </td>
                <td className="px-5 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                  {formatMillions(row.totalGapAfterMillions)}
                </td>
                <td className="px-5 py-2.5 text-right font-mono text-xs tabular-nums text-[var(--pe-color-text-tertiary)]">
                  {shortSha(row.outputH5Sha256)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BalancedFixSection() {
  const [data, setData] = useState<BalancedFixData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loadBalancedFixData()
      .then((result) => {
        if (!active) return;
        setData(result);
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Failed to load balanced-fix data.",
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

  const metrics = useMemo(() => {
    const rows = data?.rows ?? [];
    if (rows.length === 0) return null;
    const peakBenefitCut = rows.reduce(
      (best, row) => (row.benefitCutPct > best.benefitCutPct ? row : best),
      rows[0],
    );
    const peakSsRate = rows.reduce(
      (best, row) => (row.combinedSsRatePct > best.combinedSsRatePct ? row : best),
      rows[0],
    );
    const peakHiRate = rows.reduce(
      (best, row) => (row.combinedHiRatePct > best.combinedHiRatePct ? row : best),
      rows[0],
    );
    const maxResidualGap = rows.reduce(
      (best, row) =>
        Math.abs(row.totalGapAfterMillions) > Math.abs(best.totalGapAfterMillions)
          ? row
          : best,
      rows[0],
    );
    return { peakBenefitCut, peakSsRate, peakHiRate, maxResidualGap };
  }, [data]);

  if (loading) {
    return (
      <section className="flex min-h-[24rem] items-center justify-center rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
        <div className="flex items-center gap-3 text-[var(--pe-color-text-secondary)]">
          <LoaderCircle className="h-5 w-5 animate-spin" />
          <span>Loading balanced-fix data…</span>
        </div>
      </section>
    );
  }

  if (error || !data || data.rows.length === 0 || !metrics) {
    return (
      <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-error)] bg-white px-5 py-6 text-[var(--pe-color-error)]">
        {error ?? "No balanced-fix rows are available."}
      </section>
    );
  }

  return (
    <section className="space-y-7">
      <div className="border-t border-[var(--pe-color-border-light)] pt-6">
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--pe-color-primary-700)]">
          Context baseline
        </p>
        <h3 className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
          Balanced fix baseline
        </h3>
        <p className="mt-2 max-w-3xl text-base leading-7 text-[var(--pe-color-text-secondary)]">
          Annual full-H5 Option 13 outputs that close OASDI and HI gaps with a
          50 percent Social Security benefit-gap benefit reduction and remaining
          payroll-rate increases. This surface is context for comparing reform
          options, not a standard benefit-taxation revenue score.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <IntegrityFlag>Full reform H5 saved for every modeled year</IntegrityFlag>
          <IntegrityFlag>R2 upload validated</IntegrityFlag>
          <IntegrityFlag>No interpolation</IntegrityFlag>
          <IntegrityFlag>No manual weight aggregation</IntegrityFlag>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile
          label="Peak benefit cut"
          value={formatPercent(metrics.peakBenefitCut.benefitCutPct)}
          caption={`${metrics.peakBenefitCut.year}, applied to Social Security benefits`}
        />
        <MetricTile
          label="Peak OASDI rate"
          value={formatPercent(metrics.peakSsRate.combinedSsRatePct)}
          caption={`${metrics.peakSsRate.year}, combined employee and employer`}
        />
        <MetricTile
          label="Peak HI rate"
          value={formatPercent(metrics.peakHiRate.combinedHiRatePct)}
          caption={`${metrics.peakHiRate.year}, combined employee and employer`}
        />
        <MetricTile
          label="Max residual gap"
          value={formatMillions(metrics.maxResidualGap.totalGapAfterMillions)}
          caption={`${metrics.maxResidualGap.year}, after balancing`}
        />
      </div>

      <BalancedFixChart rows={data.rows} />

      <SpotlightTable rows={data.rows} />

      <div className="rounded-[var(--pe-radius-feature)] bg-[var(--pe-color-bg-secondary)] px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--pe-color-text-title)]">
              <Database className="h-4 w-4 text-[var(--pe-color-primary-700)]" />
              Artifact provenance
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--pe-color-text-secondary)]">
              Generated {formatGeneratedAt(data.metadata.generated_at)} from{" "}
              <span className="font-mono text-xs">{data.metadata.run_prefix}</span>.
              The CSV keeps the R2 raw-H5 URI, metadata URI, completion marker,
              and output hash for every exact modeled year.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <DataLink href="balanced_fix_baseline.csv" label="Data CSV" />
            <DataLink
              href="balanced_fix_baseline_metadata.json"
              label="Metadata"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
