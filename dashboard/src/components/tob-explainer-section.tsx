"use client";

import { useEffect, useMemo, useState } from "react";
import { LoaderCircle } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  loadTobExplainerData,
  type TobExplainerData,
} from "@/lib/tob-explainer-data";
import { useElementSize } from "@/lib/use-element-size";

const FILING_LABELS: Record<string, string> = {
  SINGLE: "Single",
  JOINT: "Married filing jointly",
};

function dollars(value: number): string {
  return `$${value.toLocaleString()}`;
}

function StatCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-[var(--pe-radius-container)] border border-[var(--pe-color-border-light)] bg-white px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
        {value}
      </p>
      <p className="mt-1 text-xs leading-5 text-[var(--pe-color-text-secondary)]">
        {detail}
      </p>
    </div>
  );
}

function ExplainerChart({
  chartData,
  benefitCap,
  baseCrossing,
  adjustedCrossing,
}: {
  chartData: Array<{ otherIncome: number; share: number; amount: number }>;
  benefitCap: number;
  baseCrossing: number;
  adjustedCrossing: number;
}) {
  const { ref, width } = useElementSize<HTMLDivElement>();

  return (
    <div ref={ref} className="w-full">
      {width > 0 && (
        <LineChart
          width={width}
          height={340}
          data={chartData}
          margin={{ top: 12, right: 24, bottom: 8, left: 8 }}
        >
          <CartesianGrid stroke="var(--pe-color-border-light)" vertical={false} />
          <XAxis
            dataKey="otherIncome"
            tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
            tick={{ fontSize: 12, fill: "var(--pe-color-text-tertiary)" }}
            label={{
              value: "Other income (pension, interest, withdrawals)",
              position: "insideBottom",
              offset: -2,
              fontSize: 12,
              fill: "var(--pe-color-text-secondary)",
            }}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fontSize: 12, fill: "var(--pe-color-text-tertiary)" }}
            width={44}
          />
          <Tooltip
            formatter={(value, name) => {
              const v = typeof value === "number" ? value : Number(value);
              return name === "share"
                ? [`${v.toFixed(1)}%`, "Taxable share of benefits"]
                : [dollars(v), String(name)];
            }}
            labelFormatter={(v) => `Other income ${dollars(Number(v))}`}
          />
          <ReferenceLine
            y={benefitCap * 100}
            stroke="var(--pe-color-border-medium)"
            strokeDasharray="4 4"
            label={{
              value: `${Math.round(benefitCap * 100)}% cap`,
              position: "insideTopRight",
              fontSize: 11,
              fill: "var(--pe-color-text-tertiary)",
            }}
          />
          {baseCrossing > 0 && (
            <ReferenceLine
              x={baseCrossing}
              stroke="var(--pe-color-primary-300)"
              strokeDasharray="4 4"
              label={{
                value: "50% tier begins",
                angle: -90,
                position: "insideTopLeft",
                fontSize: 11,
                fill: "var(--pe-color-text-tertiary)",
              }}
            />
          )}
          {adjustedCrossing > 0 && (
            <ReferenceLine
              x={adjustedCrossing}
              stroke="var(--pe-color-primary-500)"
              strokeDasharray="4 4"
              label={{
                value: "85% tier begins",
                angle: -90,
                position: "insideTopLeft",
                fontSize: 11,
                fill: "var(--pe-color-text-tertiary)",
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="share"
            stroke="var(--pe-color-primary-600)"
            strokeWidth={2.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      )}
    </div>
  );
}

export function TobExplainerSection() {
  const [data, setData] = useState<TobExplainerData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filingStatus, setFilingStatus] = useState<"SINGLE" | "JOINT">(
    "SINGLE",
  );
  const [ssBenefit, setSsBenefit] = useState<number>(24_000);

  useEffect(() => {
    loadTobExplainerData().then(setData, (e) => setError(String(e)));
  }, []);

  const curve = useMemo(() => {
    if (!data) return null;
    return (
      data.curves.find(
        (c) => c.filing_status === filingStatus && c.ss_benefit === ssBenefit,
      ) ?? null
    );
  }, [data, filingStatus, ssBenefit]);

  const benefitLevels = useMemo(() => {
    if (!data) return [];
    return [
      ...new Set(
        data.curves
          .filter((c) => c.filing_status === filingStatus)
          .map((c) => c.ss_benefit),
      ),
    ].sort((a, b) => a - b);
  }, [data, filingStatus]);

  if (error) {
    return (
      <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-6 text-sm text-[var(--pe-color-text-secondary)]">
        The explainer data could not be loaded. {error}
      </section>
    );
  }

  if (!data) {
    return (
      <section className="flex min-h-[16rem] items-center justify-center rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
        <div className="flex items-center gap-3 text-[var(--pe-color-text-secondary)]">
          <LoaderCircle className="h-5 w-5 animate-spin" />
          <span>Loading explainer…</span>
        </div>
      </section>
    );
  }

  const params = data.parameters;
  const baseThreshold = params.base_threshold[filingStatus];
  const adjustedThreshold = params.adjusted_base_threshold[filingStatus];
  // Combined income = other income + half of benefits, so a combined-income
  // threshold maps to an other-income position by subtracting half the benefit.
  const ssOffset = params.combined_income_ss_fraction * ssBenefit;
  const baseCrossing = Math.max(0, baseThreshold - ssOffset);
  const adjustedCrossing = Math.max(0, adjustedThreshold - ssOffset);

  const context2026 = data.context.find((c) => c.year === 2026);
  const contextFar = data.context.find((c) => c.year === 2100);
  const contextMid = data.context.find((c) => c.year === 2050);

  const chartData =
    curve?.points.map((p) => ({
      otherIncome: p.other_income,
      share: p.taxable_share * 100,
      amount: p.taxable_amount,
    })) ?? [];

  return (
    <section
      id="how-it-works"
      className="space-y-6 rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-6"
    >
      <div className="max-w-3xl">
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--pe-color-primary-700)]">
          The current system
        </p>
        <h3 className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
          How Social Security benefits are taxed today
        </h3>
        <div className="mt-3 space-y-3 text-sm leading-7 text-[var(--pe-color-text-secondary)]">
          <p>
            Since 1984, beneficiaries with income above set thresholds owe
            federal income tax on part of their benefits. The taxable share
            depends on <em>combined income</em> — adjusted gross income, plus
            tax-exempt interest, plus half of Social Security benefits.
          </p>
          <p>
            Above {dollars(baseThreshold)} of combined income (
            {FILING_LABELS[filingStatus].toLowerCase()}), up to{" "}
            {Math.round(params.base_inclusion_rate * 100)}% of benefits become
            taxable; above {dollars(adjustedThreshold)}, up to{" "}
            {Math.round(params.benefit_inclusion_cap * 100)}%. The revenue from
            the first tier goes to the Social Security trust funds, and the
            additional revenue from the second tier goes to Medicare&apos;s
            Hospital Insurance trust fund.
          </p>
          <p>
            Because the thresholds were fixed in nominal dollars in 1983 and
            1993 and have never been indexed, benefit growth and inflation pull
            more beneficiaries above them every year — which is why the share
            of households paying this tax rises under current law even with no
            change in policy. The 2025 reconciliation act&apos;s senior
            deduction reduces many older filers&apos; overall income tax
            through 2028, but does not change these inclusion rules.
          </p>
        </div>
      </div>

      {context2026 && contextFar && (
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard
            label={`In ${context2026.year}`}
            value={`${Math.round(
              context2026.share_of_beneficiary_households_paying * 100,
            )}%`}
            detail={`of beneficiary households pay some tax on benefits, raising $${(
              context2026.tob_oasdi_billions +
              context2026.tob_medicare_hi_billions
            ).toFixed(0)}B ($${context2026.tob_oasdi_billions.toFixed(0)}B to Social Security, $${context2026.tob_medicare_hi_billions.toFixed(0)}B to Medicare).`}
          />
          {contextMid && (
            <StatCard
              label={`By ${contextMid.year}`}
              value={`${Math.round(
                contextMid.share_of_beneficiary_households_paying * 100,
              )}%`}
              detail={`of beneficiary households pay, raising $${Math.round(
                contextMid.tob_oasdi_billions + contextMid.tob_medicare_hi_billions,
              ).toLocaleString()}B under current law.`}
            />
          )}
          <StatCard
            label={`By ${contextFar.year}`}
            value={`${Math.round(
              contextFar.share_of_beneficiary_households_paying * 100,
            )}%`}
            detail={`of beneficiary households pay, raising $${Math.round(
              contextFar.tob_oasdi_billions + contextFar.tob_medicare_hi_billions,
            ).toLocaleString()}B under current law.`}
          />
        </div>
      )}

      <div className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h4 className="text-base font-semibold text-[var(--pe-color-text-title)]">
              What share of a retiree&apos;s benefits is taxable?
            </h4>
            <p className="mt-1 text-sm text-[var(--pe-color-text-secondary)]">
              Each point is a policyengine-us simulation of a retired{" "}
              {filingStatus === "JOINT" ? "couple" : "filer"} under{" "}
              {data.curve_year} law, varying non-benefit income.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Filing status"
              value={filingStatus}
              onChange={(e) =>
                setFilingStatus(e.target.value as "SINGLE" | "JOINT")
              }
              className="rounded-[var(--pe-radius-element)] border border-[var(--pe-color-border-medium)] bg-white px-3 py-1.5 text-sm text-[var(--pe-color-text-primary)]"
            >
              {Object.entries(FILING_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <select
              aria-label="Annual Social Security benefit"
              value={ssBenefit}
              onChange={(e) => setSsBenefit(Number(e.target.value))}
              className="rounded-[var(--pe-radius-element)] border border-[var(--pe-color-border-medium)] bg-white px-3 py-1.5 text-sm text-[var(--pe-color-text-primary)]"
            >
              {benefitLevels.map((level) => (
                <option key={level} value={level}>
                  {dollars(level)}/yr in benefits
                </option>
              ))}
            </select>
          </div>
        </div>

        <ExplainerChart
          chartData={chartData}
          benefitCap={params.benefit_inclusion_cap}
          baseCrossing={baseCrossing}
          adjustedCrossing={adjustedCrossing}
        />
        <p className="text-xs leading-5 text-[var(--pe-color-text-tertiary)]">
          Thresholds and inclusion rates from {params.source}. Computed with
          policyengine-us {data.policyengine_us_version}; population shares from
          the calibrated baseline datasets.
        </p>
      </div>
    </section>
  );
}
