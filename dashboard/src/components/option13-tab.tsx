"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useElementSize } from "@/lib/use-element-size";
import {
  loadOption13Data,
  loadTrusteesComparisonData,
  type Option13Data,
  type TrusteesComparisonData,
} from "@/lib/option13-data";

const CURRENT_SS_RATE = 0.062;
const CURRENT_HI_RATE = 0.0145;

function billions(value: number) {
  return Math.abs(value / 1e9);
}

function formatB(value: number) {
  return `$${Math.round(value).toLocaleString()}B`;
}

function Metric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "negative";
}) {
  const toneClass =
    tone === "positive"
      ? "text-[var(--pe-color-primary-700)]"
      : tone === "negative"
        ? "text-[var(--pe-color-error)]"
        : "text-[var(--pe-color-text-primary)]";

  return (
    <div className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-4 shadow-[0_18px_48px_rgba(16,24,40,0.06)]">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--pe-color-text-tertiary)]">
        {label}
      </p>
      <p className={`mt-3 text-2xl font-semibold ${toneClass}`}>{value}</p>
    </div>
  );
}

function Option13Chart({
  title,
  description,
  data,
  bars,
  yFormatter,
}: {
  title: string;
  description: string;
  data: Array<Record<string, number | string>>;
  bars: Array<{ dataKey: string; name: string; color: string }>;
  yFormatter?: (value: number) => string;
}) {
  const { ref, width, height } = useElementSize<HTMLDivElement>();

  return (
    <div className="min-w-0 rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-5 shadow-[0_18px_48px_rgba(16,24,40,0.06)]">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-[var(--pe-color-text-title)]">
          {title}
        </h3>
        <p className="mt-1 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
          {description}
        </p>
      </div>
      <div ref={ref} className="h-[20rem]">
        {width > 0 && height > 0 ? (
          <BarChart width={width} height={height} data={data} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--pe-color-border-light)" strokeDasharray="4 4" vertical={false} />
              <XAxis
                dataKey="year"
                tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="number"
                tickCount={5}
                niceTicks="snap125"
                tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={yFormatter}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: "12px",
                  border: "1px solid var(--pe-color-border-light)",
                  boxShadow: "0 18px 48px rgba(16, 24, 40, 0.12)",
                }}
              />
              <Legend />
              {bars.map((bar) => (
                <Bar
                  key={bar.dataKey}
                  dataKey={bar.dataKey}
                  name={bar.name}
                  fill={bar.color}
                  radius={[6, 6, 0, 0]}
                />
              ))}
            </BarChart>
        ) : null}
      </div>
    </div>
  );
}

export function Option13Tab() {
  const [data, setData] = useState<Option13Data[]>([]);
  const [trusteesData, setTrusteesData] = useState<TrusteesComparisonData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    Promise.all([loadOption13Data(), loadTrusteesComparisonData()])
      .then(([option13Data, trusteesComparisonData]) => {
        if (!active) return;
        setData(option13Data);
        setTrusteesData(trusteesComparisonData);
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(caughtError instanceof Error ? caughtError.message : "Failed to load Option 13 data.");
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const derived = useMemo(() => {
    return data.map((row) => ({
      year: row.year,
      benefitCutPct: (1 - row.benefitMultiplier) * 100,
      ssRateIncrease: (row.newEmployeeSsRate - CURRENT_SS_RATE) * 100 * 2,
      hiRateIncrease: (row.newEmployeeHiRate - CURRENT_HI_RATE) * 100 * 2,
      ssGapBefore: billions(row.baselineSsGap),
      ssGapAfter: billions(row.ssGapAfter),
      hiGapBefore: billions(row.baselineHiGap),
      hiGapAfter: billions(row.hiGapAfter),
      combinedGapBefore: billions(row.baselineSsGap + row.baselineHiGap),
      combinedGapAfter: billions(row.totalGapAfter),
      currentSsRate: row.newEmployeeSsRate * 2 * 100,
      currentHiRate: row.newEmployeeHiRate * 2 * 100,
    }));
  }, [data]);

  if (loading) {
    return (
      <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-6 text-[var(--pe-color-text-secondary)] shadow-[0_18px_48px_rgba(16,24,40,0.08)]">
        Loading Balanced Fix baseline...
      </section>
    );
  }

  if (error || data.length === 0) {
    return (
      <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-error)] bg-white px-5 py-6 text-[var(--pe-color-error)] shadow-[0_18px_48px_rgba(16,24,40,0.08)]">
        {error ?? "No Option 13 data available."}
      </section>
    );
  }

  const firstYear = derived[0];

  return (
    <div className="space-y-6">
      <section className="rounded-[var(--pe-radius-feature)] border border-white/70 bg-[rgba(255,255,255,0.74)] px-5 py-5 shadow-[0_18px_48px_rgba(16,24,40,0.08)] backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--pe-color-text-tertiary)]">
          Balanced fix baseline
        </p>
        <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-[var(--pe-color-text-title)]">
          Option 13: Balanced Fix Baseline
        </h2>
        <p className="mt-3 max-w-4xl text-base leading-7 text-[var(--pe-color-text-secondary)]">
          This baseline scenario closes trust-fund gaps starting in 2035 using the traditional fix
          approach: Social Security uses a 50/50 mix of benefit cuts and payroll-tax increases,
          while HI is closed entirely with payroll-tax increases. Unlike Options 1-12, it does not
          include the employer payroll tax reform.
        </p>
      </section>

      <section className="grid gap-4 xl:grid-cols-4">
        <Metric label="Benefit cut (2035)" value={`${firstYear.benefitCutPct.toFixed(1)}%`} tone="negative" />
        <Metric label="SS tax increase (2035)" value={`+${firstYear.ssRateIncrease.toFixed(2)}pp`} tone="positive" />
        <Metric label="HI tax increase (2035)" value={`+${firstYear.hiRateIncrease.toFixed(2)}pp`} tone="positive" />
        <Metric
          label="Combined gap (2035)"
          value={`${formatB(firstYear.combinedGapBefore)} → ${formatB(firstYear.combinedGapAfter)}`}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Option13Chart
          title="Benefit cuts by year"
          description="Benefit reduction required to close half of the Social Security shortfall."
          data={derived}
          bars={[{ dataKey: "benefitCutPct", name: "Benefit cut", color: "#ef4444" }]}
          yFormatter={(value) => `${value.toFixed(0)}%`}
        />
        <Option13Chart
          title="Payroll tax rate increases"
          description="Combined employee and employer rate increases under the balanced-fix baseline."
          data={derived}
          bars={[
            { dataKey: "ssRateIncrease", name: "SS increase (pp)", color: "#319795" },
            { dataKey: "hiRateIncrease", name: "HI increase (pp)", color: "#64748b" },
          ]}
          yFormatter={(value) => `${value.toFixed(1)}pp`}
        />
        <Option13Chart
          title="Social Security trust-fund gap"
          description="Gap before the reform versus the residual gap after the balanced-fix baseline."
          data={derived}
          bars={[
            { dataKey: "ssGapBefore", name: "Before", color: "#ef4444" },
            { dataKey: "ssGapAfter", name: "After", color: "#319795" },
          ]}
          yFormatter={(value) => `$${Math.round(value)}`}
        />
        <Option13Chart
          title="Medicare HI trust-fund gap"
          description="HI gap before the reform versus the residual gap after the balanced-fix baseline."
          data={derived}
          bars={[
            { dataKey: "hiGapBefore", name: "Before", color: "#ef4444" },
            { dataKey: "hiGapAfter", name: "After", color: "#319795" },
          ]}
          yFormatter={(value) => `$${Math.round(value)}`}
        />
      </section>

      <Option13Chart
        title="Combined trust-fund gap"
        description="Total OASDI plus HI shortfall before and after the balanced-fix baseline."
        data={derived}
        bars={[
          { dataKey: "combinedGapBefore", name: "Before", color: "#ef4444" },
          { dataKey: "combinedGapAfter", name: "After", color: "#319795" },
        ]}
        yFormatter={(value) => `$${Math.round(value)}`}
      />

      <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-5 shadow-[0_18px_48px_rgba(16,24,40,0.06)]">
        <h3 className="text-xl font-semibold text-[var(--pe-color-text-title)]">
          Detailed results by year
        </h3>
        <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
          This table pairs Option 13 reform parameters with the Trustees-versus-PolicyEngine gap comparison.
        </p>

        <div className="mt-4 overflow-x-auto rounded-[var(--pe-radius-container)] border border-[var(--pe-color-border-light)]">
          <table className="min-w-[72rem] divide-y divide-[var(--pe-color-border-light)] text-sm">
            <thead className="bg-[var(--pe-color-bg-secondary)] text-[var(--pe-color-text-secondary)]">
              <tr>
                <th rowSpan={2} className="px-4 py-3 text-left">Year</th>
                <th colSpan={3} className="px-4 py-3 text-center">Option 13 reforms</th>
                <th colSpan={4} className="px-4 py-3 text-center">OASDI gap ($B)</th>
                <th colSpan={4} className="px-4 py-3 text-center">HI gap ($B)</th>
              </tr>
              <tr>
                <th className="px-4 py-3 text-right">Benefit cut</th>
                <th className="px-4 py-3 text-right">SS rate</th>
                <th className="px-4 py-3 text-right">HI rate</th>
                <th className="px-4 py-3 text-right">Trustees</th>
                <th className="px-4 py-3 text-right">PE before</th>
                <th className="px-4 py-3 text-right">PE/TR</th>
                <th className="px-4 py-3 text-right">PE after</th>
                <th className="px-4 py-3 text-right">Trustees</th>
                <th className="px-4 py-3 text-right">PE before</th>
                <th className="px-4 py-3 text-right">PE/TR</th>
                <th className="px-4 py-3 text-right">PE after</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--pe-color-border-light)] bg-white">
              {data.map((row, index) => {
                const trusteesRow = trusteesData.find((candidate) => candidate.year === row.year);
                const ssGap = derived[index].ssGapBefore;
                const hiGap = derived[index].hiGapBefore;
                const ssRatio =
                  trusteesRow && trusteesRow.trusteesOasdiGapB !== 0
                    ? Math.abs(ssGap) / trusteesRow.trusteesOasdiGapB
                    : null;
                const hiRatio =
                  trusteesRow && trusteesRow.trusteesHiGapB > 0
                    ? Math.abs(hiGap) / trusteesRow.trusteesHiGapB
                    : null;

                return (
                  <tr key={row.year}>
                    <td className="px-4 py-3 font-medium text-[var(--pe-color-text-primary)]">{row.year}</td>
                    <td className="px-4 py-3 text-right text-[var(--pe-color-error)]">{derived[index].benefitCutPct.toFixed(1)}%</td>
                    <td className="px-4 py-3 text-right">{derived[index].currentSsRate.toFixed(2)}%</td>
                    <td className="px-4 py-3 text-right">{derived[index].currentHiRate.toFixed(2)}%</td>
                    <td className="px-4 py-3 text-right">-{formatB(trusteesRow?.trusteesOasdiGapB ?? 0)}</td>
                    <td className="px-4 py-3 text-right">-{formatB(ssGap)}</td>
                    <td className="px-4 py-3 text-right">{ssRatio ? `${ssRatio.toFixed(2)}x` : "—"}</td>
                    <td className="px-4 py-3 text-right text-[var(--pe-color-primary-700)]">{formatB(derived[index].ssGapAfter)}</td>
                    <td className="px-4 py-3 text-right">-{formatB(trusteesRow?.trusteesHiGapB ?? 0)}</td>
                    <td className="px-4 py-3 text-right">-{formatB(hiGap)}</td>
                    <td className="px-4 py-3 text-right">{hiRatio ? `${hiRatio.toFixed(2)}x` : "—"}</td>
                    <td className="px-4 py-3 text-right text-[var(--pe-color-primary-700)]">{formatB(derived[index].hiGapAfter)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-4 space-y-1 text-sm text-[var(--pe-color-text-secondary)]">
          <p>
            <strong>Legend:</strong> Trustees = SSA Trustees projection, PE = PolicyEngine microsimulation, PE/TR = ratio.
          </p>
          <p>
            <strong>Signs:</strong> negative values indicate deficits and positive after-values indicate the remaining balance after the reform package.
          </p>
        </div>
      </section>

      <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-5 shadow-[0_18px_48px_rgba(16,24,40,0.06)]">
        <h3 className="text-xl font-semibold text-[var(--pe-color-text-title)]">
          Methodology: step-by-step gap closing
        </h3>
        <div className="mt-4 space-y-5 text-sm leading-7 text-[var(--pe-color-text-secondary)]">
          <div>
            <h4 className="font-semibold text-[var(--pe-color-text-primary)]">Step 1: Calculate baseline gaps</h4>
            <p>Run PolicyEngine under current law to measure Social Security and HI trust-fund gaps.</p>
          </div>
          <div>
            <h4 className="font-semibold text-[var(--pe-color-text-primary)]">Step 2: Apply 50% benefit cuts</h4>
            <p>Reduce Social Security benefits enough to close half of the Social Security shortfall, allowing TOB feedback to flow through naturally.</p>
          </div>
          <div>
            <h4 className="font-semibold text-[var(--pe-color-text-primary)]">Step 3: Measure remaining gaps</h4>
            <p>Recalculate remaining OASDI and HI shortfalls after the benefit-cut stage.</p>
          </div>
          <div>
            <h4 className="font-semibold text-[var(--pe-color-text-primary)]">Step 4: Calculate rate increases</h4>
            <p>Use taxable payroll to determine the payroll-tax increases needed to close the remaining gaps.</p>
          </div>
          <div>
            <h4 className="font-semibold text-[var(--pe-color-text-primary)]">Step 5: Apply rate increases and verify</h4>
            <p>Split rate increases evenly between employee and employer and verify that the final gaps are approximately zero.</p>
          </div>
          <div>
            <h4 className="font-semibold text-[var(--pe-color-text-primary)]">Key design decisions</h4>
            <ul className="ml-5 list-disc space-y-1">
              <li>No employer payroll tax reform in the baseline.</li>
              <li>Social Security uses 50% benefit cuts and 50% payroll-tax increases.</li>
              <li>HI uses payroll-tax increases rather than Medicare benefit cuts.</li>
              <li>The two-stage approach measures actual post-benefit-cut gaps instead of estimating TOB losses upfront.</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}
