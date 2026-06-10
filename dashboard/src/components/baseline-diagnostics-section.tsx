"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, Download, LoaderCircle } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  DIAGNOSTICS_PANELS,
  diagnosticsDataHref,
  loadBaselineDiagnostics,
  type BaselineDiagnosticsRow,
  type DiagnosticsPanel,
} from "@/lib/baseline-diagnostics-data";
import { useElementSize } from "@/lib/use-element-size";

const SPOTLIGHT_YEARS = [2026, 2050, 2075, 2100];

function formatValue(
  value: number | null | undefined,
  unit: DiagnosticsPanel["unit"],
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "–";
  }
  switch (unit) {
    case "trillions":
      return `$${(value / 1e12).toLocaleString(undefined, {
        maximumFractionDigits: 1,
      })}T`;
    case "billions":
      return `$${(value / 1e9).toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })}B`;
    case "millions":
      return `${(value / 1e6).toLocaleString(undefined, {
        maximumFractionDigits: 1,
      })}M`;
    case "percent":
      return `${(value * 100).toLocaleString(undefined, {
        maximumFractionDigits: 1,
      })}%`;
  }
}

function axisFormatter(unit: DiagnosticsPanel["unit"]) {
  return (value: number) => formatValue(value, unit);
}

function panelRows(
  rows: BaselineDiagnosticsRow[],
  panel: DiagnosticsPanel,
): Array<Record<string, number | null>> {
  return rows.map((row) => {
    const out: Record<string, number | null> = { year: row.year };
    if (panel.ratio) {
      const numerator = row[panel.ratio.numerator];
      const denominator = row[panel.ratio.denominator];
      out.ratio =
        numerator !== null &&
        denominator !== null &&
        denominator !== 0 &&
        numerator !== undefined &&
        denominator !== undefined
          ? numerator / denominator
          : null;
    }
    for (const series of panel.series) {
      out[series.key] = row[series.key] ?? null;
    }
    return out;
  });
}

function DiagnosticsChart({
  rows,
  panel,
}: {
  rows: BaselineDiagnosticsRow[];
  panel: DiagnosticsPanel;
}) {
  const { ref, width } = useElementSize<HTMLDivElement>();
  const data = useMemo(() => panelRows(rows, panel), [rows, panel]);
  const chartWidth = Math.max(width, 280);

  return (
    <div className="rounded-lg border border-border bg-card p-4" ref={ref}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium text-foreground">{panel.title}</h4>
        <span
          className={
            panel.calibrated
              ? "rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary"
              : "rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
          }
        >
          {panel.calibrated ? "calibrated" : "diagnostic"}
        </span>
      </div>
      <LineChart
        width={chartWidth}
        height={200}
        data={data}
        margin={{ top: 12, right: 8, bottom: 0, left: 8 }}
      >
        <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" />
        <XAxis
          dataKey="year"
          tick={{ fontSize: 11 }}
          ticks={[2026, 2050, 2075, 2100]}
        />
        <YAxis
          tickFormatter={axisFormatter(panel.unit)}
          tick={{ fontSize: 11 }}
          width={64}
        />
        <Tooltip
          formatter={(value) => formatValue(Number(value), panel.unit)}
          labelFormatter={(year) => `Year ${year}`}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {panel.ratio ? (
          <Line
            type="monotone"
            dataKey="ratio"
            name={panel.ratio.label}
            stroke="var(--chart-1)"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        ) : null}
        {panel.series.map((series) => (
          <Line
            key={series.key}
            type="monotone"
            dataKey={series.key}
            name={series.label}
            stroke={series.color}
            strokeWidth={series.dashed ? 1.5 : 2}
            strokeDasharray={series.dashed ? "6 4" : undefined}
            dot={false}
            connectNulls
          />
        ))}
      </LineChart>
      {panel.note ? (
        <p className="mt-2 text-xs text-muted-foreground">{panel.note}</p>
      ) : null}
    </div>
  );
}

export function BaselineDiagnosticsSection() {
  const [rows, setRows] = useState<BaselineDiagnosticsRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadBaselineDiagnostics()
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((cause: Error) => {
        if (!cancelled) setError(cause.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return null; // diagnostics are additive; hide the section if data is absent
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" aria-hidden />
          <h3 className="text-lg font-semibold text-foreground">
            Baseline trajectories through 2100
          </h3>
        </div>
        <a
          className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
          href={diagnosticsDataHref}
          download
        >
          <Download className="h-4 w-4" aria-hidden />
          Download the full series
        </a>
      </div>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Every panel shows the baseline datasets simulated at each modeled
        year. Solid lines are model output; dashed lines are 2026 Trustees
        Report targets or references. Panels marked “calibrated” are matched
        exactly during dataset construction; “diagnostic” panels are
        unconstrained by-products shown so divergences are visible rather
        than hidden — including federal income tax, whose level runs above
        administrative collections (a known enhanced-CPS property) while its
        growth path should stay smooth.
      </p>
      {rows === null ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden />
          Loading baseline diagnostics…
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {DIAGNOSTICS_PANELS.map((panel) => (
              <DiagnosticsChart key={panel.id} rows={rows} panel={panel} />
            ))}
          </div>
          <SpotlightTable rows={rows} />
        </>
      )}
    </section>
  );
}

function SpotlightTable({ rows }: { rows: BaselineDiagnosticsRow[] }) {
  const spotlight = SPOTLIGHT_YEARS.map((year) =>
    rows.find((row) => row.year === year),
  ).filter((row): row is BaselineDiagnosticsRow => Boolean(row));
  if (!spotlight.length) return null;

  const lines: Array<{
    label: string;
    key: string;
    unit: DiagnosticsPanel["unit"];
    targetKey?: string;
  }> = [
    { label: "Population", key: "population", unit: "millions", targetKey: "target_population" },
    { label: "SS benefits", key: "social_security", unit: "trillions", targetKey: "target_social_security" },
    { label: "Taxable payroll", key: "ssa_taxable_payroll", unit: "trillions", targetKey: "target_ssa_taxable_payroll" },
    { label: "OASDI TOB", key: "tob_revenue_oasdi", unit: "billions", targetKey: "target_tob_revenue_oasdi" },
    { label: "HI TOB", key: "tob_revenue_medicare_hi", unit: "billions", targetKey: "target_tob_revenue_medicare_hi" },
    { label: "Income tax", key: "income_tax", unit: "trillions" },
    { label: "AGI", key: "adjusted_gross_income", unit: "trillions" },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 pr-4 font-medium">Series</th>
            {spotlight.map((row) => (
              <th key={row.year} className="py-2 pr-4 font-medium">
                {row.year}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line.key} className="border-b border-border/60">
              <td className="py-2 pr-4 text-foreground">{line.label}</td>
              {spotlight.map((row) => {
                const value = row[line.key];
                const target = line.targetKey ? row[line.targetKey] : null;
                const gap =
                  target && value !== null && value !== undefined && target !== 0
                    ? (value as number) / (target as number) - 1
                    : null;
                return (
                  <td key={row.year} className="py-2 pr-4">
                    <span className="text-foreground">
                      {formatValue(value as number, line.unit)}
                    </span>
                    {gap !== null && Math.abs(gap) >= 0.0005 ? (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({gap > 0 ? "+" : ""}
                        {(gap * 100).toFixed(1)}% vs target)
                      </span>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
