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

function DecileBars({
  rows,
  basis,
}: {
  rows: DecileImpact[];
  basis: Basis;
}) {
  const { ref, width } = useElementSize<HTMLDivElement>();
  const data = rows.map((r) => ({
    decile: r.decile,
    value: basis === "avg_change" ? r.avg_change : r.pct_change,
  }));
  const fmt = (v: number) =>
    basis === "avg_change"
      ? `${v >= 0 ? "+$" : "-$"}${Math.abs(Math.round(v)).toLocaleString()}`
      : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

  return (
    <div ref={ref} className="w-full">
      {width > 0 && (
        <BarChart
          width={width}
          height={320}
          data={data}
          margin={{ top: 12, right: 16, bottom: 24, left: 8 }}
        >
          <CartesianGrid stroke="var(--pe-color-border-light)" vertical={false} />
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
            formatter={(value) => [fmt(Number(value)), "Change in net income"]}
            labelFormatter={(d) => `Decile ${d}`}
            cursor={{ fill: "var(--pe-color-bg-secondary)" }}
          />
          <ReferenceLine y={0} stroke="var(--pe-color-border-medium)" />
          <Bar dataKey="value" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell
                key={d.decile}
                fill={
                  d.value >= 0
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
  if (upper === undefined) return byYear[String(sorted[sorted.length - 1])] ?? [];
  const lo = byYear[String(lower)];
  const hi = byYear[String(upper)];
  if (!lo || !hi) return lo ?? hi ?? [];
  const t = upper === lower ? 0 : (year - lower) / (upper - lower);
  return lo.map((row, i) => {
    const other = hi[i];
    return {
      decile: row.decile,
      avg_change: row.avg_change + t * (other.avg_change - row.avg_change),
      pct_change: row.pct_change + t * (other.pct_change - row.pct_change),
      total_change_billions:
        row.total_change_billions +
        t * (other.total_change_billions - row.total_change_billions),
    };
  });
}

export function DistributionalSection({
  reformId,
  reformName,
}: {
  reformId: string;
  reformName: string;
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
  // slider scrubs every year in range and non-anchor years are interpolated.
  const year =
    selectedYear !== null && minYear !== null && maxYear !== null
      ? Math.min(Math.max(selectedYear, minYear), maxYear)
      : (minYear ?? null);
  const isAnchor = year !== null && years.includes(year);

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
          <div className="flex items-center gap-3">
            <div className="flex items-baseline gap-1.5">
              <span className="text-lg font-semibold tabular-nums text-[var(--pe-color-text-title)]">
                {year}
              </span>
              <span
                className={`text-[10px] font-medium uppercase tracking-[0.12em] ${
                  isAnchor
                    ? "text-[var(--pe-color-primary-700)]"
                    : "text-[var(--pe-color-text-tertiary)]"
                }`}
              >
                {isAnchor ? "modeled" : "interpolated"}
              </span>
            </div>
            <input
              type="range"
              aria-label="Year"
              min={minYear}
              max={maxYear}
              step={1}
              value={year}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
              className="w-44 accent-[var(--pe-color-primary-600)]"
            />
          </div>
        </div>
      </div>

      <div className="mt-4">
        <DecileBars rows={rows} basis={basis} />
      </div>

      <p className="mt-3 text-xs leading-5 text-[var(--pe-color-text-tertiary)]">
        Deciles rank households by baseline net income, computed from the saved
        reform microdata against a baseline simulation. Modeled years (2026,
        2030, then every fifth year) use full microsimulation output;
        in-between years are linearly interpolated for display, as on the
        revenue path.
      </p>
    </section>
  );
}
