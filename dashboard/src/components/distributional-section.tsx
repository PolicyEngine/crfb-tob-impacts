"use client";

import { useEffect, useMemo, useState } from "react";
import { LoaderCircle } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  loadDistributionalData,
  type DecileImpact,
  type DistributionalData,
} from "@/lib/distributional-data";
import { useElementSize } from "@/lib/use-element-size";

type Basis = "avg_change" | "pct_change";

function DecileBars({ rows, basis }: { rows: DecileImpact[]; basis: Basis }) {
  const { ref, width } = useElementSize<HTMLDivElement>();
  const data = rows.map((r) => ({
    decile: r.decile,
    // null values (suppressed percentages) render no bar, keeping the axis sane.
    value: basis === "avg_change" ? r.avg_change : r.pct_change,
  }));
  const fmt = (v: number | null) => {
    if (v === null || !Number.isFinite(v)) return "n/a";
    return basis === "avg_change"
      ? `${v >= 0 ? "+$" : "-$"}${Math.abs(Math.round(v)).toLocaleString()}`
      : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
  };

  return (
    <div ref={ref} className="w-full">
      {width > 0 && (
        <BarChart
          width={width}
          height={320}
          data={data}
          margin={{ top: 12, right: 16, bottom: 24, left: 8 }}
        >
          <CartesianGrid
            stroke="var(--pe-color-border-light)"
            vertical={false}
          />
          <XAxis
            dataKey="decile"
            tick={{ fontSize: 12, fill: "var(--pe-color-text-tertiary)" }}
            label={{
              value: "Household net income decile (1 = lowest)",
              position: "insideBottom",
              offset: -10,
              fontSize: 12,
              fill: "var(--pe-color-text-secondary)",
            }}
          />
          <YAxis
            tickFormatter={fmt}
            tick={{ fontSize: 12, fill: "var(--pe-color-text-tertiary)" }}
            width={64}
          />
          <Tooltip
            formatter={(value) => [
              fmt(value === null || value === undefined ? null : Number(value)),
              "Change in net income",
            ]}
            labelFormatter={(d) => `Decile ${d}`}
            cursor={{ fill: "var(--pe-color-bg-secondary)" }}
          />
          <ReferenceLine y={0} stroke="var(--pe-color-border-medium)" />
          <Bar dataKey="value" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell
                key={d.decile}
                fill={
                  (d.value ?? 0) >= 0
                    ? "var(--pe-color-primary-500)"
                    : "var(--pe-color-error)"
                }
              />
            ))}
          </Bar>
        </BarChart>
      )}
    </div>
  );
}

function interpolateDeciles(
  byYear: Record<string, DecileImpact[]>,
  anchors: number[],
  year: number,
): DecileImpact[] {
  if (byYear[String(year)]) return byYear[String(year)];
  const sorted = [...anchors].sort((a, b) => a - b);
  const lower = [...sorted].reverse().find((y) => y <= year);
  const upper = sorted.find((y) => y >= year);
  if (lower === undefined) return byYear[String(sorted[0])] ?? [];
  if (upper === undefined)
    return byYear[String(sorted[sorted.length - 1])] ?? [];
  const lo = byYear[String(lower)];
  const hi = byYear[String(upper)];
  if (!lo || !hi) return lo ?? hi ?? [];
  const t = upper === lower ? 0 : (year - lower) / (upper - lower);
  const hiByDecile = new Map(hi.map((r) => [r.decile, r]));
  const lerp = (a: number, b: number) => a + t * (b - a);
  return lo.map((row) => {
    const other = hiByDecile.get(row.decile) ?? row;
    // Percent change is suppressed (null) for some deciles; only interpolate
    // when both endpoints are defined, otherwise keep it null.
    const pct =
      row.pct_change === null || other.pct_change === null
        ? null
        : lerp(row.pct_change, other.pct_change);
    return {
      decile: row.decile,
      avg_change: lerp(row.avg_change, other.avg_change),
      pct_change: pct,
      total_change_billions: lerp(
        row.total_change_billions,
        other.total_change_billions,
      ),
    };
  });
}

export function DistributionalSection({
  reformId,
  reformName,
  staticScoringNote = false,
}: {
  reformId: string;
  reformName: string;
  // Set when the dashboard is showing labor-response figures: the decile
  // data is computed from static scoring, and the caption says so.
  staticScoringNote?: boolean;
}) {
  const [data, setData] = useState<DistributionalData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [basis, setBasis] = useState<Basis>("avg_change");

  useEffect(() => {
    loadDistributionalData().then(setData, (e) => setError(String(e)));
  }, []);

  const years = useMemo(() => data?.anchor_years ?? [], [data]);
  const minYear = years.length ? Math.min(...years) : null;
  const maxYear = years.length ? Math.max(...years) : null;
  // Derive the effective year rather than syncing it through an effect; the
  // dropdown only offers exact anchor years, so every selection is modeled.
  const year =
    selectedYear !== null && minYear !== null && maxYear !== null
      ? Math.min(Math.max(selectedYear, minYear), maxYear)
      : (minYear ?? null);

  if (error || (data && !data.data[reformId])) {
    return null; // distributional data not available for this reform
  }
  if (!data || year === null || minYear === null || maxYear === null) {
    return (
      <section className="flex min-h-[12rem] items-center justify-center rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
        <div className="flex items-center gap-3 text-[var(--pe-color-text-secondary)]">
          <LoaderCircle className="h-5 w-5 animate-spin" />
          <span>Loading distribution…</span>
        </div>
      </section>
    );
  }

  const rows = interpolateDeciles(data.data[reformId] ?? {}, years, year);

  return (
    <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h4 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
            Who is affected, by income decile
          </h4>
          <p className="mt-1 text-sm text-[var(--pe-color-text-secondary)]">
            Average change in household net income under {reformName}, by
            baseline income decile, in {year}.
            {staticScoringNote ? " Deciles use static scoring." : null}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="inline-flex overflow-hidden rounded-[var(--pe-radius-element)] border border-[var(--pe-color-border-medium)] text-sm">
            <button
              onClick={() => setBasis("avg_change")}
              className={`px-3 py-1.5 ${
                basis === "avg_change"
                  ? "bg-[var(--pe-color-primary-600)] text-white"
                  : "bg-white text-[var(--pe-color-text-primary)]"
              }`}
            >
              $ change
            </button>
            <button
              onClick={() => setBasis("pct_change")}
              className={`px-3 py-1.5 ${
                basis === "pct_change"
                  ? "bg-[var(--pe-color-primary-600)] text-white"
                  : "bg-white text-[var(--pe-color-text-primary)]"
              }`}
            >
              % change
            </button>
          </div>
          <label className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--pe-color-text-secondary)]">
              Year
            </span>
            <select
              aria-label="Year"
              value={year}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
              className="rounded-[var(--pe-radius-element)] border border-[var(--pe-color-border-medium)] bg-white px-3 py-1.5 text-sm font-semibold tabular-nums text-[var(--pe-color-text-title)] transition focus:border-[var(--pe-color-primary-500)] focus:outline-none"
            >
              {Array.from(
                { length: maxYear - minYear + 1 },
                (_, i) => minYear + i,
              ).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="mt-4">
        <DecileBars rows={rows} basis={basis} />
      </div>

      {basis === "pct_change" && rows.some((r) => r.pct_change === null) ? (
        <p className="mt-2 text-xs text-[var(--pe-color-text-tertiary)]">
          Deciles whose aggregate baseline net income is not positive are
          omitted from the percentage view, where a percent change is undefined.
        </p>
      ) : null}

      <p className="mt-3 text-xs leading-5 text-[var(--pe-color-text-tertiary)]">
        Deciles rank households by baseline net income, computed from the saved
        reform microdata against a baseline simulation. Each year shown is
        computed directly from full reform microsimulation output.
      </p>
    </section>
  );
}
