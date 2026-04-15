"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import {
  BookOpenText,
  Download,
  LoaderCircle,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { useEffect, useMemo, useState } from "react";
import { Header, logos } from "@policyengine/ui-kit";

import { ComparisonTable } from "@/components/comparison-table";
import { MethodologySection } from "@/components/methodology-section";
import { Option13Tab } from "@/components/option13-tab";
import { PaperTab } from "@/components/paper-tab";
import {
  ALLOCATION_ELIGIBLE_OPTIONS,
  calculateTotals,
  type AllocationMode,
  type DisplayUnit,
  loadDashboardData,
  spotlightRows,
  type ScoringType,
  type YearlyImpact,
} from "@/lib/dashboard-data";
import { EXTERNAL_ESTIMATES, REFORMS, type ReformMeta } from "@/lib/reforms";
import { useElementSize } from "@/lib/use-element-size";

type DashboardTab = "reforms" | "option13" | "paper";
type ViewMode = "10year" | "75year";

const STANDARD_REFORMS = REFORMS.filter((reform) => reform.id !== "option13");
const LONG_RUN_X_AXIS_TICKS = [
  2026,
  ...Array.from({ length: (2100 - 2030) / 5 + 1 }, (_, index) => 2030 + index * 5),
];

function formatBillions(value: number) {
  const rounded = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1);
  return `${value >= 0 ? "$" : "-$"}${Math.abs(Number(rounded)).toLocaleString()}B`;
}

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatValue(value: number, displayUnit: DisplayUnit) {
  if (displayUnit === "dollars") return formatBillions(value);
  return formatPercent(value);
}

function formatTooltipEntry(
  value: ValueType | undefined,
  name: NameType | undefined,
  displayUnit: DisplayUnit,
): [string, string] {
  const numericValue =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number.parseFloat(value)
        : NaN;

  const formattedValue = Number.isFinite(numericValue)
    ? formatValue(numericValue, displayUnit)
    : "n/a";

  const label =
    name === "total" ? "Total" : name === "oasdi" ? "OASDI" : "HI";

  return [formattedValue, label];
}

function getSeriesValue(row: YearlyImpact, displayUnit: DisplayUnit, key: "total" | "oasdi" | "hi") {
  if (displayUnit === "dollars") {
    if (key === "total") return row.revenueImpact;
    if (key === "oasdi") return row.tobOasdiImpact;
    return row.tobMedicareHiImpact;
  }

  if (displayUnit === "pctPayroll") {
    if (key === "total") return row.pctOfOasdiPayroll;
    if (key === "oasdi") return row.oasdiPctOfPayroll;
    return row.hiPctOfPayroll;
  }

  if (key === "total") return row.pctOfGdp;
  if (key === "oasdi") return row.oasdiPctOfGdp;
  return row.hiPctOfGdp;
}

function isPositive(value: number) {
  return value >= 0;
}

function MetricTile({
  label,
  value,
  tone = "neutral",
  caption,
  accent = false,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "negative";
  caption?: string;
  accent?: boolean;
}) {
  const toneClass =
    tone === "positive"
      ? "text-[var(--pe-color-primary-700)]"
      : tone === "negative"
        ? "text-[var(--pe-color-error)]"
        : "text-[var(--pe-color-text-primary)]";

  return (
    <div
      className={`rounded-[var(--pe-radius-feature)] px-5 py-4 ${
        accent
          ? "border-l-[3px] border-l-[var(--pe-color-primary-500)] bg-white shadow-[0_12px_28px_rgba(16,24,40,0.06)]"
          : "bg-[var(--pe-color-bg-secondary)]"
      }`}
    >
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
        {label}
      </p>
      <p className={`mt-2 text-2xl font-bold tracking-[-0.02em] ${toneClass}`}>{value}</p>
      {caption ? (
        <p className="mt-1.5 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
          {caption}
        </p>
      ) : null}
    </div>
  );
}

function SeriesChart({
  data,
  displayUnit,
  viewMode,
}: {
  data: YearlyImpact[];
  displayUnit: DisplayUnit;
  viewMode: ViewMode;
}) {
  const { ref, width, height } = useElementSize<HTMLDivElement>();
  const xAxisTicks =
    viewMode === "75year" ? LONG_RUN_X_AXIS_TICKS : undefined;

  const chartData = data.map((row) => ({
    year: row.year,
    total: getSeriesValue(row, displayUnit, "total"),
    oasdi: getSeriesValue(row, displayUnit, "oasdi"),
    hi: getSeriesValue(row, displayUnit, "hi"),
  }));

  return (
    <div className="min-w-0 rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <h3 className="text-xl font-bold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
          Revenue and trust-fund effects
        </h3>
        <p className="text-sm text-[var(--pe-color-text-tertiary)]">
          {displayUnit === "dollars"
            ? "Billions of nominal dollars"
            : displayUnit === "pctPayroll"
              ? "% of taxable payroll"
              : "% of GDP"}
        </p>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-[var(--pe-color-text-secondary)]">
        <span className="flex items-center gap-1.5"><span className="inline-block h-[3px] w-4 rounded-full bg-[var(--pe-color-text-primary)]" />Total</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-[3px] w-4 rounded-full bg-[var(--pe-color-primary-500)]" />OASDI</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-[3px] w-4 rounded-full bg-[var(--pe-color-gray-500)]" />HI</span>
      </div>

      <div ref={ref} className="h-[24rem]">
        {width > 0 && height > 0 ? (
          <AreaChart width={width} height={height} data={chartData} margin={{ top: 12, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="oasdiFill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="var(--pe-color-primary-500)" stopOpacity={0.34} />
                  <stop offset="100%" stopColor="var(--pe-color-primary-500)" stopOpacity={0.04} />
                </linearGradient>
                <linearGradient id="hiFill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="var(--pe-color-gray-500)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--pe-color-gray-500)" stopOpacity={0.04} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--pe-color-border-light)" strokeDasharray="4 4" vertical={false} />
              <XAxis
                dataKey="year"
                ticks={xAxisTicks}
                interval={viewMode === "75year" ? 0 : undefined}
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
                tickFormatter={(value: number) =>
                  displayUnit === "dollars" ? `$${Math.round(value)}` : `${value.toFixed(1)}%`
                }
              />
              <Tooltip
                contentStyle={{
                  borderRadius: "12px",
                  border: "1px solid var(--pe-color-border-light)",
                  boxShadow: "0 18px 48px rgba(16, 24, 40, 0.12)",
                }}
                formatter={(value, name) =>
                  formatTooltipEntry(value, name, displayUnit)
                }
              />
              <Area
                type="monotone"
                dataKey="oasdi"
                stroke="var(--pe-color-primary-500)"
                fill="url(#oasdiFill)"
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="hi"
                stroke="var(--pe-color-gray-500)"
                fill="url(#hiFill)"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke="var(--pe-color-text-primary)"
                strokeWidth={2.5}
                dot={false}
              />
            </AreaChart>
        ) : null}
      </div>
    </div>
  );
}

function ReformBrief({
  reform,
  scoringType,
}: {
  reform: ReformMeta;
  scoringType: ScoringType;
}) {
  return (
    <motion.section
      key={`${reform.id}-${scoringType}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-5 shadow-[0_18px_48px_rgba(16,24,40,0.06)]"
    >
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--pe-color-text-tertiary)]">
            Selected reform · {reform.category}
          </p>
          <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[var(--pe-color-text-title)]">
            {reform.name}
          </h3>
          <p className="mt-3 text-base leading-7 text-[var(--pe-color-text-secondary)]">
            {reform.description}
          </p>
        </div>
        <div className="shrink-0 rounded-full bg-[var(--pe-color-primary-50)] px-4 py-2 text-sm font-semibold text-[var(--pe-color-primary-800)]">
          {scoringType === "dynamic" ? "Conventional dynamic view" : "Static view"}
        </div>
      </div>

      <div className="mt-5 grid gap-4 border-t border-[var(--pe-color-border-light)] pt-5 lg:grid-cols-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--pe-color-text-tertiary)]">
            What changes
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
            {reform.mechanism}
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--pe-color-text-tertiary)]">
            Baseline context
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
            {reform.baseline}
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--pe-color-text-tertiary)]">
            How to read it
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
            {reform.interpretation} {reform.scoringNote}
          </p>
        </div>
      </div>
    </motion.section>
  );
}

export function DashboardShell() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("reforms");
  const [selectedReform, setSelectedReform] = useState("option1");
  const [scoringType, setScoringType] = useState<ScoringType>("static");
  const [allocationMode, setAllocationMode] =
    useState<AllocationMode>("baselineShares");
  const [displayUnit, setDisplayUnit] = useState<DisplayUnit>("dollars");
  const [viewMode, setViewMode] = useState<ViewMode>("10year");
  const [data, setData] = useState<Record<string, YearlyImpact[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isEmbedded = useMemo(
    () => typeof window !== "undefined" && window.self !== window.top,
    [],
  );

  useEffect(() => {
    let active = true;

    loadDashboardData(scoringType, allocationMode)
      .then((result) => {
        if (!active) return;
        setData(result);
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Failed to load dashboard data.",
        );
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [allocationMode, scoringType]);

  function handleScoringTypeChange(next: ScoringType) {
    setLoading(true);
    setError(null);
    setScoringType(next);
  }

  function handleAllocationModeChange(next: AllocationMode) {
    setLoading(true);
    setError(null);
    setAllocationMode(next);
  }

  function handleViewModeChange(next: ViewMode) {
    setViewMode(next);
    setDisplayUnit(next === "10year" ? "dollars" : "pctPayroll");
  }

  const reform = STANDARD_REFORMS.find((candidate) => candidate.id === selectedReform) as ReformMeta;
  const selectedData = data[selectedReform] ?? [];
  const visibleData =
    viewMode === "10year"
      ? selectedData.filter((row) => row.year >= 2026 && row.year <= 2035)
      : selectedData;
  const totals = calculateTotals(selectedData);
  const spotlight = spotlightRows(selectedData);
  const showAllocationToggle = ALLOCATION_ELIGIBLE_OPTIONS.includes(selectedReform);
  const estimates = EXTERNAL_ESTIMATES[selectedReform] ?? [];
  const baseline2026 = selectedData.find((row) => row.year === 2026);

  function exportCsv() {
    if (selectedData.length === 0) return;
    const headers = [
      "Reform",
      "Year",
      "Revenue Impact ($B)",
      "OASDI Impact ($B)",
      "HI Impact ($B)",
      "Total TOB Impact ($B)",
    ];
    const rows = selectedData.map((row) => [
      reform.name,
      String(row.year),
      row.revenueImpact.toFixed(2),
      row.tobOasdiImpact.toFixed(2),
      row.tobMedicareHiImpact.toFixed(2),
      row.tobTotalImpact.toFixed(2),
    ]);
    const content = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");
    const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedReform}_impact_data.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--pe-color-text-primary)]">
      {!isEmbedded && (
        <Header
          variant="dark"
          logo={
            <Image
              src={logos.whiteWordmark}
              alt="PolicyEngine"
              width={140}
              height={20}
              className="h-5 w-auto"
              priority
            />
          }
        >
          <span className="ml-2 font-bold text-white">Taxation of benefits reforms</span>
        </Header>
      )}
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className="mx-auto flex max-w-[1600px] gap-6 px-4 py-6 sm:px-6"
      >
        <aside className="hidden w-[17rem] shrink-0 self-start xl:sticky xl:top-4 xl:block">
          <nav className="space-y-5">
            <div>
              <h3 className="px-1 text-xs font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
                Benefit tax rules
              </h3>
              <div className="mt-2 space-y-0.5">
                {STANDARD_REFORMS.filter((r) =>
                  ["option1", "option2", "option3", "option4", "option7", "option8", "option9", "option10", "option11"].includes(r.id),
                ).map((option) => {
                  const active = option.id === selectedReform && activeTab === "reforms";
                  return (
                    <button
                      key={option.id}
                      onClick={() => {
                        setActiveTab("reforms");
                        setSelectedReform(option.id);
                      }}
                      className={`flex w-full items-center gap-2 rounded-[var(--pe-radius-element)] px-3 py-2 text-left text-sm transition ${
                        active
                          ? "bg-[var(--pe-color-primary-50)] font-semibold text-[var(--pe-color-primary-800)]"
                          : "text-[var(--pe-color-text-secondary)] hover:bg-[var(--pe-color-bg-secondary)] hover:text-[var(--pe-color-text-primary)]"
                      }`}
                    >
                      {active && <span className="h-4 w-0.5 shrink-0 rounded-full bg-[var(--pe-color-primary-500)]" />}
                      <span>{option.shortName}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <h3 className="px-1 text-xs font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
                Structural swaps
              </h3>
              <div className="mt-2 space-y-0.5">
                {STANDARD_REFORMS.filter((r) =>
                  ["option5", "option6", "option12", "option14_stacked"].includes(r.id),
                ).map((option) => {
                  const active = option.id === selectedReform && activeTab === "reforms";
                  return (
                    <button
                      key={option.id}
                      onClick={() => {
                        setActiveTab("reforms");
                        setSelectedReform(option.id);
                      }}
                      className={`flex w-full items-center gap-2 rounded-[var(--pe-radius-element)] px-3 py-2 text-left text-sm transition ${
                        active
                          ? "bg-[var(--pe-color-primary-50)] font-semibold text-[var(--pe-color-primary-800)]"
                          : "text-[var(--pe-color-text-secondary)] hover:bg-[var(--pe-color-bg-secondary)] hover:text-[var(--pe-color-text-primary)]"
                      }`}
                    >
                      {active && <span className="h-4 w-0.5 shrink-0 rounded-full bg-[var(--pe-color-primary-500)]" />}
                      <span>{option.shortName}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <h3 className="px-1 text-xs font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
                Publication
              </h3>
              <div className="mt-2 space-y-0.5">
                <button
                  onClick={() => setActiveTab("paper")}
                  className={`flex w-full items-center gap-2 rounded-[var(--pe-radius-element)] px-3 py-2 text-left text-sm transition ${
                    activeTab === "paper"
                      ? "bg-[var(--pe-color-primary-50)] font-semibold text-[var(--pe-color-primary-800)]"
                      : "text-[var(--pe-color-text-secondary)] hover:bg-[var(--pe-color-bg-secondary)] hover:text-[var(--pe-color-text-primary)]"
                  }`}
                >
                  {activeTab === "paper" && <span className="h-4 w-0.5 shrink-0 rounded-full bg-[var(--pe-color-primary-500)]" />}
                  <span>Citable paper</span>
                </button>
              </div>
            </div>
          </nav>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col gap-6">
          {/* --- Editorial surface: no border, no shadow, whitespace-driven --- */}
          <section className="px-1 py-2">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <h2 className="text-4xl font-bold tracking-[-0.04em] text-[var(--pe-color-text-title)] sm:text-5xl">
                  Social Security taxation reform
                </h2>
                <p className="mt-4 max-w-2xl text-lg leading-8 text-[var(--pe-color-text-secondary)]">
                  Policy options for reforming the taxation of Social Security benefits, with budgetary impacts through 2100. Analysis commissioned by the Committee for a Responsible Federal Budget.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => setActiveTab("paper")}
                  className="inline-flex items-center gap-2 rounded-full border border-[var(--pe-color-border-medium)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--pe-color-text-primary)] transition hover:border-[var(--pe-color-primary-300)] hover:text-[var(--pe-color-primary-700)]"
                >
                  <BookOpenText className="h-4 w-4" />
                  Read paper
                </button>
                {activeTab === "reforms" ? (
                  <button
                    onClick={exportCsv}
                    className="inline-flex items-center gap-2 rounded-full border border-[var(--pe-color-border-medium)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--pe-color-text-primary)] transition hover:border-[var(--pe-color-primary-300)] hover:text-[var(--pe-color-primary-700)]"
                  >
                    <Download className="h-4 w-4" />
                    Export CSV
                  </button>
                ) : null}
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-4">
              <div className="inline-flex rounded-full border border-[var(--pe-color-border-medium)] bg-white p-1">
                <button
                  onClick={() => setActiveTab("reforms")}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    activeTab === "reforms"
                      ? "bg-[var(--pe-color-primary-600)] text-white"
                      : "text-[var(--pe-color-text-secondary)] hover:text-[var(--pe-color-text-primary)]"
                  }`}
                >
                  TOB reform options
                </button>
                <button
                  onClick={() => setActiveTab("option13")}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    activeTab === "option13"
                      ? "bg-[var(--pe-color-primary-600)] text-white"
                      : "text-[var(--pe-color-text-secondary)] hover:text-[var(--pe-color-text-primary)]"
                  }`}
                >
                  Balanced Fix baseline
                </button>
                <button
                  onClick={() => setActiveTab("paper")}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    activeTab === "paper"
                      ? "bg-[var(--pe-color-primary-600)] text-white"
                      : "text-[var(--pe-color-text-secondary)] hover:text-[var(--pe-color-text-primary)]"
                  }`}
                >
                  Paper
                </button>
              </div>
            </div>
          </section>

          {/* --- Controls surface: tinted bg, compact --- */}
          {activeTab === "reforms" ? (
          <section className="rounded-[var(--pe-radius-feature)] bg-[var(--pe-color-bg-secondary)] px-5 py-4">
            <div className="xl:hidden">
              <label
                htmlFor="reform-select"
                className="text-xs font-medium uppercase tracking-[0.18em] text-[var(--pe-color-text-tertiary)]"
              >
                Reform option
              </label>
              <select
                id="reform-select"
                value={selectedReform}
                onChange={(event) => setSelectedReform(event.target.value)}
                className="mt-2 w-full rounded-[var(--pe-radius-container)] border border-[var(--pe-color-border-light)] bg-white px-4 py-3 text-sm font-medium text-[var(--pe-color-text-primary)] outline-none transition focus:border-[var(--pe-color-primary-400)]"
              >
                {STANDARD_REFORMS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.shortName}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="grid gap-3 sm:grid-cols-2 xl:flex">
                <Segment
                  label="Scoring"
                  value={scoringType}
                  onChange={(next) => handleScoringTypeChange(next as ScoringType)}
                  options={[
                    { label: "Static", value: "static" },
                    { label: "Conventional", value: "dynamic" },
                  ]}
                />
                {showAllocationToggle ? (
                  <Segment
                    label="Trust fund split"
                    value={allocationMode}
                    onChange={(next) =>
                      handleAllocationModeChange(next as AllocationMode)
                    }
                    options={[
                      { label: "Current law", value: "currentLaw" },
                      { label: "Baseline shares", value: "baselineShares" },
                    ]}
                  />
                ) : null}
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:flex">
                <Segment
                  label="Unit"
                  value={displayUnit}
                  onChange={(next) => setDisplayUnit(next as DisplayUnit)}
                  options={[
                    { label: "$", value: "dollars" },
                    { label: "% payroll", value: "pctPayroll" },
                    { label: "% GDP", value: "pctGdp" },
                  ]}
                />
                <Segment
                  label="Period"
                  value={viewMode}
                  onChange={(next) => handleViewModeChange(next as ViewMode)}
                  options={[
                    { label: "10-year", value: "10year" },
                    { label: "75-year", value: "75year" },
                  ]}
                />
              </div>
            </div>
          </section>
          ) : null}

          {activeTab === "reforms" ? (
            <ReformBrief reform={reform} scoringType={scoringType} />
          ) : null}

          {activeTab === "paper" ? (
            <PaperTab />
          ) : activeTab === "option13" ? (
            <Option13Tab />
          ) : loading ? (
            <section className="flex min-h-[24rem] items-center justify-center rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white shadow-[0_18px_48px_rgba(16,24,40,0.08)]">
              <div className="flex items-center gap-3 text-[var(--pe-color-text-secondary)]">
                <LoaderCircle className="h-5 w-5 animate-spin" />
                <span>Loading policy impact data...</span>
              </div>
            </section>
          ) : error ? (
            <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-error)] bg-white px-5 py-6 text-[var(--pe-color-error)] shadow-[0_18px_48px_rgba(16,24,40,0.08)]">
              {error}
            </section>
          ) : selectedData.length === 0 ? (
            <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-6 text-[var(--pe-color-text-secondary)] shadow-[0_18px_48px_rgba(16,24,40,0.08)]">
              No {scoringType} results are available for {reform.shortName}.
            </section>
          ) : (
            <>
              <section className="grid gap-4 xl:grid-cols-4">
                <MetricTile
                  label="10-year effect"
                  value={formatValue(
                    displayUnit === "dollars" ? totals.tenYear : displayUnit === "pctPayroll" ? totals.tenYearPctPayroll : totals.tenYearPctGdp,
                    displayUnit,
                  )}
                  tone={isPositive(totals.tenYear) ? "positive" : "negative"}
                  caption="2026-2035 cumulative"
                  accent
                />
                <MetricTile
                  label="75-year effect"
                  value={formatValue(
                    displayUnit === "dollars" ? totals.total : displayUnit === "pctPayroll" ? totals.totalPctPayroll : totals.totalPctGdp,
                    displayUnit,
                  )}
                  tone={isPositive(totals.total) ? "positive" : "negative"}
                  caption="2026-2100 cumulative"
                  accent
                />
                <MetricTile
                  label="2026 baseline TOB"
                  value={baseline2026 ? formatBillions(baseline2026.baselineTobTotal) : "n/a"}
                  caption="Current-law baseline"
                />
                <MetricTile
                  label="OASDI / HI split"
                  value={
                    baseline2026
                      ? `${Math.round((baseline2026.baselineTobOasdi / baseline2026.baselineTobTotal) * 100)} / ${Math.round((baseline2026.baselineTobMedicareHi / baseline2026.baselineTobTotal) * 100)}`
                      : "n/a"
                  }
                  caption="2026 baseline share"
                />
              </section>

              <section className="grid gap-6 2xl:grid-cols-[minmax(0,1.7fr)_minmax(22rem,0.9fr)]">
                <SeriesChart
                  data={visibleData}
                  displayUnit={displayUnit}
                  viewMode={viewMode}
                />

                <div className="min-w-0 space-y-6">
                  {/* --- Dense data surface: table with minimal wrapping --- */}
                  <div className="overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)]">
                    <div className="bg-[var(--pe-color-bg-secondary)] px-5 py-3">
                      <h4 className="text-sm font-semibold text-[var(--pe-color-text-title)]">Spotlight years</h4>
                    </div>
                    <table className="min-w-full divide-y divide-[var(--pe-color-border-light)] text-sm">
                      <thead className="text-[var(--pe-color-text-secondary)]">
                        <tr>
                          <th className="px-5 py-2.5 text-left font-medium">Year</th>
                          <th className="px-5 py-2.5 text-right font-medium">Total</th>
                          <th className="px-5 py-2.5 text-right font-medium">OASDI</th>
                          <th className="px-5 py-2.5 text-right font-medium">HI</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--pe-color-border-light)] bg-white">
                        {spotlight.map((row) => (
                          <tr key={row.year}>
                            <td className="px-5 py-2.5 font-medium text-[var(--pe-color-text-primary)]">
                              {row.year}
                            </td>
                            <td className="px-5 py-2.5 text-right font-semibold text-[var(--pe-color-text-primary)]">
                              {formatValue(getSeriesValue(row, displayUnit, "total"), displayUnit)}
                            </td>
                            <td className="px-5 py-2.5 text-right text-[var(--pe-color-primary-700)]">
                              {formatValue(getSeriesValue(row, displayUnit, "oasdi"), displayUnit)}
                            </td>
                            <td className="px-5 py-2.5 text-right text-[var(--pe-color-text-secondary)]">
                              {formatValue(getSeriesValue(row, displayUnit, "hi"), displayUnit)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="rounded-[var(--pe-radius-feature)] bg-[var(--pe-color-bg-secondary)] px-5 py-5">
                    <h4 className="text-sm font-semibold text-[var(--pe-color-text-title)]">
                      External checks
                    </h4>
                    {estimates.length > 0 ? (
                      <div className="mt-4 space-y-3">
                        {estimates.map((estimate) => (
                          <a
                            key={`${estimate.source}-${estimate.budgetWindow}`}
                            className="block rounded-[var(--pe-radius-container)] border border-[var(--pe-color-border-light)] px-4 py-3 transition hover:border-[var(--pe-color-primary-300)] hover:bg-[var(--pe-color-primary-50)]"
                            href={estimate.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <p className="font-medium text-[var(--pe-color-text-primary)]">
                                  {estimate.source}
                                </p>
                                <p className="mt-1 text-sm text-[var(--pe-color-text-secondary)]">
                                  {estimate.scoringType} · {estimate.budgetWindow}
                                </p>
                              </div>
                              <p className="text-sm font-semibold text-[var(--pe-color-text-primary)]">
                                {formatBillions(estimate.tenYearImpact)}
                              </p>
                            </div>
                          </a>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-4 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
                        No linked external estimate is attached to this reform yet.
                      </p>
                    )}
                  </div>
                </div>
              </section>

              <ComparisonTable
                reformId={selectedReform}
                policyEngineEstimate={Math.round(totals.tenYear * 10) / 10}
              />

              <MethodologySection />
            </>
          )}

          <footer className="border-t border-[var(--pe-color-border-light)] px-1 pt-6 pb-2 text-sm text-[var(--pe-color-text-tertiary)]">
            <p>
              Analysis by{" "}
              <a href="https://policyengine.org" target="_blank" rel="noreferrer" className="text-[var(--pe-color-primary-700)] hover:underline">
                PolicyEngine
              </a>
              , commissioned by the Committee for a Responsible Federal Budget.
              {" "}Data: 2025 Social Security Trustees Report.
            </p>
          </footer>
        </main>
      </motion.div>
    </div>
  );
}



function Segment({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--pe-color-text-tertiary)]">
        {label}
      </p>
      <div className="inline-flex rounded-full border border-[var(--pe-color-border-medium)] bg-white p-1 shadow-[0_6px_18px_rgba(16,24,40,0.05)]">
        {options.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              onClick={() => onChange(option.value)}
              className={`rounded-full px-3.5 py-2 text-sm font-medium transition ${
                active
                  ? "bg-[var(--pe-color-primary-600)] text-white"
                  : "text-[var(--pe-color-text-secondary)] hover:text-[var(--pe-color-text-primary)]"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
