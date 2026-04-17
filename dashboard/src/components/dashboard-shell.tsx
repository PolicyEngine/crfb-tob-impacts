"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { BookOpenText, Download, ExternalLink, LoaderCircle } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { useEffect, useState } from "react";
import { Header, logos } from "@policyengine/ui-kit";

import { ComparisonTable } from "@/components/comparison-table";
import { MethodologySection } from "@/components/methodology-section";
import { Option13Tab } from "@/components/option13-tab";
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

type DashboardTab = "reforms" | "option13";
type ViewMode = "10year" | "75year";

const STANDARD_REFORMS = REFORMS.filter((reform) => reform.id !== "option13");

const BENEFIT_RULE_IDS = [
  "option1",
  "option2",
  "option3",
  "option4",
  "option7",
  "option8",
  "option9",
  "option10",
  "option11",
];
const STRUCTURAL_IDS = ["option5", "option6", "option12", "option14_stacked"];

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

  const label = name === "total" ? "Total" : name === "oasdi" ? "OASDI" : "HI";
  return [formattedValue, label];
}

function getSeriesValue(
  row: YearlyImpact,
  displayUnit: DisplayUnit,
  key: "total" | "oasdi" | "hi",
) {
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
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
        {label}
      </p>
      <p className={`mt-2 text-[28px] font-bold leading-none tracking-[-0.02em] ${toneClass}`}>
        {value}
      </p>
      {caption ? (
        <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
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
  const xAxisTicks = viewMode === "75year" ? LONG_RUN_X_AXIS_TICKS : undefined;

  const chartData = data.map((row) => ({
    year: row.year,
    total: getSeriesValue(row, displayUnit, "total"),
    oasdi: getSeriesValue(row, displayUnit, "oasdi"),
    hi: getSeriesValue(row, displayUnit, "hi"),
  }));

  const unitLabel =
    displayUnit === "dollars"
      ? "Billions of nominal dollars"
      : displayUnit === "pctPayroll"
        ? "Percent of taxable payroll"
        : "Percent of GDP";

  return (
    <div className="min-w-0 rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-6 py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-lg font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
          Annual revenue path
        </h3>
        <p className="text-xs text-[var(--pe-color-text-tertiary)]">{unitLabel}</p>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-[var(--pe-color-text-secondary)]">
        <LegendSwatch color="var(--pe-color-text-primary)" label="Total" />
        <LegendSwatch color="var(--pe-color-primary-500)" label="OASDI" />
        <LegendSwatch color="var(--pe-color-gray-500)" label="HI" />
      </div>

      <div ref={ref} className="mt-4 h-[22rem]">
        {width > 0 && height > 0 ? (
          <AreaChart
            width={width}
            height={height}
            data={chartData}
            margin={{ top: 8, right: 12, bottom: 0, left: 4 }}
          >
            <defs>
              <linearGradient id="oasdiFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--pe-color-primary-500)" stopOpacity={0.28} />
                <stop offset="100%" stopColor="var(--pe-color-primary-500)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="hiFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--pe-color-gray-500)" stopOpacity={0.22} />
                <stop offset="100%" stopColor="var(--pe-color-gray-500)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              stroke="var(--pe-color-border-light)"
              strokeDasharray="3 5"
              vertical={false}
            />
            <XAxis
              dataKey="year"
              ticks={xAxisTicks}
              interval={viewMode === "75year" ? 0 : undefined}
              tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="number"
              tickCount={5}
              niceTicks="snap125"
              tick={{ fill: "var(--pe-color-text-secondary)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) =>
                displayUnit === "dollars" ? `$${Math.round(value)}` : `${value.toFixed(1)}%`
              }
            />
            <ReferenceLine
              y={0}
              stroke="var(--pe-color-border-medium)"
              strokeWidth={1}
            />
            <Tooltip
              contentStyle={{
                borderRadius: "12px",
                border: "1px solid var(--pe-color-border-light)",
                boxShadow: "0 18px 48px rgba(16, 24, 40, 0.12)",
                fontSize: "13px",
              }}
              formatter={(value, name) => formatTooltipEntry(value, name, displayUnit)}
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

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-[3px] w-4 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function Segment<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: Array<{ label: string; value: T }>;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-full bg-[var(--pe-color-bg-secondary)] p-1"
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={`rounded-full px-3 py-1.5 text-[13px] font-medium transition ${
              active
                ? "bg-white text-[var(--pe-color-primary-700)] shadow-[0_2px_6px_rgba(16,24,40,0.08)]"
                : "text-[var(--pe-color-text-secondary)] hover:text-[var(--pe-color-text-primary)]"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function ControlLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="mr-2 text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
      {children}
    </span>
  );
}

function SidebarNavItem({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-2 rounded-[var(--pe-radius-element)] px-3 py-2 text-left text-sm transition ${
        active
          ? "bg-[var(--pe-color-primary-50)] font-semibold text-[var(--pe-color-primary-800)]"
          : "text-[var(--pe-color-text-secondary)] hover:bg-[var(--pe-color-bg-secondary)] hover:text-[var(--pe-color-text-primary)]"
      }`}
    >
      {active && (
        <span className="h-4 w-0.5 shrink-0 rounded-full bg-[var(--pe-color-primary-500)]" />
      )}
      <span>{label}</span>
    </button>
  );
}

function SidebarGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="px-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
        {title}
      </h3>
      <div className="mt-2 space-y-0.5">{children}</div>
    </div>
  );
}

export function DashboardShell() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("reforms");
  const [selectedReform, setSelectedReform] = useState("option1");
  const [scoringType, setScoringType] = useState<ScoringType>("static");
  const [allocationMode, setAllocationMode] = useState<AllocationMode>("baselineShares");
  const [displayUnit, setDisplayUnit] = useState<DisplayUnit>("dollars");
  const [viewMode, setViewMode] = useState<ViewMode>("10year");
  const [data, setData] = useState<Record<string, YearlyImpact[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isEmbedded =
    typeof window !== "undefined" && window.self !== window.top;

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

  const reform = STANDARD_REFORMS.find(
    (candidate) => candidate.id === selectedReform,
  ) as ReformMeta;
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
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="mx-auto flex max-w-[1500px] gap-8 px-4 py-8 sm:px-6"
      >
        {/* ------------ Sidebar ------------ */}
        <aside className="hidden w-[16rem] shrink-0 self-start xl:sticky xl:top-4 xl:block">
          <nav className="space-y-5">
            <SidebarGroup title="Benefit tax rules">
              {STANDARD_REFORMS.filter((r) => BENEFIT_RULE_IDS.includes(r.id)).map(
                (option) => (
                  <SidebarNavItem
                    key={option.id}
                    active={
                      option.id === selectedReform && activeTab === "reforms"
                    }
                    label={option.shortName}
                    onClick={() => {
                      setActiveTab("reforms");
                      setSelectedReform(option.id);
                    }}
                  />
                ),
              )}
            </SidebarGroup>

            <SidebarGroup title="Structural swaps">
              {STANDARD_REFORMS.filter((r) => STRUCTURAL_IDS.includes(r.id)).map(
                (option) => (
                  <SidebarNavItem
                    key={option.id}
                    active={
                      option.id === selectedReform && activeTab === "reforms"
                    }
                    label={option.shortName}
                    onClick={() => {
                      setActiveTab("reforms");
                      setSelectedReform(option.id);
                    }}
                  />
                ),
              )}
            </SidebarGroup>

            <SidebarGroup title="Context">
              <SidebarNavItem
                active={activeTab === "option13"}
                label="Balanced Fix baseline"
                onClick={() => setActiveTab("option13")}
              />
              <a
                href="/paper/"
                target="_blank"
                rel="noreferrer"
                className="flex w-full items-center justify-between gap-2 rounded-[var(--pe-radius-element)] px-3 py-2 text-sm text-[var(--pe-color-text-secondary)] transition hover:bg-[var(--pe-color-bg-secondary)] hover:text-[var(--pe-color-text-primary)]"
              >
                <span>Citable paper</span>
                <ExternalLink className="h-3 w-3 opacity-60" />
              </a>
            </SidebarGroup>
          </nav>
        </aside>

        {/* ------------ Main ------------ */}
        <main className="flex min-w-0 flex-1 flex-col gap-8">
          {/* Hero */}
          <section>
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <h2 className="text-4xl font-bold tracking-[-0.04em] text-[var(--pe-color-text-title)] sm:text-[44px]">
                  {activeTab === "option13"
                    ? "Balanced Fix baseline"
                    : "Social Security taxation reform"}
                </h2>
                <p className="mt-4 max-w-2xl text-lg leading-8 text-[var(--pe-color-text-secondary)]">
                  {activeTab === "option13" ? (
                    <>
                      A solvency baseline beginning in 2035 that combines
                      proportional benefit reductions with payroll-tax increases.
                      Context for interpreting the standard reform options.
                    </>
                  ) : (
                    <>
                      Budgetary impacts of reforming the taxation of Social
                      Security benefits through 2100. Commissioned by the{" "}
                      <span className="font-semibold text-[var(--pe-color-text-primary)]">
                        Committee for a Responsible Federal Budget
                      </span>
                      .
                    </>
                  )}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <a
                  href="/paper/"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-[var(--pe-color-border-medium)] bg-white px-4 py-2 text-sm font-medium text-[var(--pe-color-text-primary)] transition hover:border-[var(--pe-color-primary-300)] hover:text-[var(--pe-color-primary-700)]"
                >
                  <BookOpenText className="h-4 w-4" />
                  Read paper
                </a>
                {activeTab === "reforms" && selectedData.length > 0 && (
                  <button
                    onClick={exportCsv}
                    className="inline-flex items-center gap-2 rounded-full border border-[var(--pe-color-border-medium)] bg-white px-4 py-2 text-sm font-medium text-[var(--pe-color-text-primary)] transition hover:border-[var(--pe-color-primary-300)] hover:text-[var(--pe-color-primary-700)]"
                  >
                    <Download className="h-4 w-4" />
                    Export CSV
                  </button>
                )}
              </div>
            </div>
          </section>

          {activeTab === "option13" ? (
            <Option13Tab />
          ) : loading ? (
            <section className="flex min-h-[24rem] items-center justify-center rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
              <div className="flex items-center gap-3 text-[var(--pe-color-text-secondary)]">
                <LoaderCircle className="h-5 w-5 animate-spin" />
                <span>Loading policy impact data…</span>
              </div>
            </section>
          ) : error ? (
            <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-error)] bg-white px-5 py-6 text-[var(--pe-color-error)]">
              {error}
            </section>
          ) : selectedData.length === 0 ? (
            <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-6 text-[var(--pe-color-text-secondary)]">
              No {scoringType} results are available for {reform.shortName}.
            </section>
          ) : (
            <>
              {/* Mobile reform picker — sidebar is xl-only */}
              <section className="xl:hidden">
                <label
                  htmlFor="reform-select"
                  className="block text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]"
                >
                  Reform option
                </label>
                <select
                  id="reform-select"
                  value={selectedReform}
                  onChange={(event) => setSelectedReform(event.target.value)}
                  className="mt-2 w-full rounded-[var(--pe-radius-container)] border border-[var(--pe-color-border-light)] bg-white px-4 py-3 text-sm font-medium text-[var(--pe-color-text-primary)] outline-none transition focus:border-[var(--pe-color-primary-400)]"
                >
                  <optgroup label="Benefit tax rules">
                    {STANDARD_REFORMS.filter((r) => BENEFIT_RULE_IDS.includes(r.id)).map(
                      (option) => (
                        <option key={option.id} value={option.id}>
                          {option.shortName}
                        </option>
                      ),
                    )}
                  </optgroup>
                  <optgroup label="Structural swaps">
                    {STANDARD_REFORMS.filter((r) => STRUCTURAL_IDS.includes(r.id)).map(
                      (option) => (
                        <option key={option.id} value={option.id}>
                          {option.shortName}
                        </option>
                      ),
                    )}
                  </optgroup>
                </select>
              </section>

              {/* Reform name + category band — a slim editorial surface, no card */}
              <section className="border-t border-[var(--pe-color-border-light)] pt-6">
                <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--pe-color-primary-700)]">
                      {reform.category}
                    </p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-[var(--pe-color-text-title)]">
                      {reform.name}
                    </h3>
                    <p className="mt-2 max-w-3xl text-base leading-7 text-[var(--pe-color-text-secondary)]">
                      {reform.description}
                    </p>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--pe-color-text-tertiary)]">
                      {reform.mechanism}
                    </p>
                  </div>
                  <span className="inline-flex shrink-0 items-center rounded-full bg-[var(--pe-color-bg-secondary)] px-3 py-1 text-xs font-medium text-[var(--pe-color-text-secondary)]">
                    {scoringType === "dynamic" ? "Conventional dynamic" : "Static scoring"}
                  </span>
                </div>
              </section>

              {/* Controls — compact inline row */}
              <section className="flex flex-wrap items-center gap-x-6 gap-y-3">
                <div className="flex items-center">
                  <ControlLabel>Scoring</ControlLabel>
                  <Segment
                    label="Scoring"
                    value={scoringType}
                    onChange={handleScoringTypeChange}
                    options={[
                      { label: "Static", value: "static" },
                      { label: "Conventional", value: "dynamic" },
                    ]}
                  />
                </div>
                <div className="flex items-center">
                  <ControlLabel>Unit</ControlLabel>
                  <Segment
                    label="Unit"
                    value={displayUnit}
                    onChange={setDisplayUnit}
                    options={[
                      { label: "$", value: "dollars" },
                      { label: "% payroll", value: "pctPayroll" },
                      { label: "% GDP", value: "pctGdp" },
                    ]}
                  />
                </div>
                <div className="flex items-center">
                  <ControlLabel>Period</ControlLabel>
                  <Segment
                    label="Period"
                    value={viewMode}
                    onChange={handleViewModeChange}
                    options={[
                      { label: "10-year", value: "10year" },
                      { label: "75-year", value: "75year" },
                    ]}
                  />
                </div>
                {showAllocationToggle && (
                  <div className="flex items-center">
                    <ControlLabel>Trust fund split</ControlLabel>
                    <Segment
                      label="Trust fund split"
                      value={allocationMode}
                      onChange={handleAllocationModeChange}
                      options={[
                        { label: "Current law", value: "currentLaw" },
                        { label: "Baseline shares", value: "baselineShares" },
                      ]}
                    />
                  </div>
                )}
              </section>

              {/* Metrics */}
              <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <MetricTile
                  label="10-year effect"
                  value={formatValue(
                    displayUnit === "dollars"
                      ? totals.tenYear
                      : displayUnit === "pctPayroll"
                        ? totals.tenYearPctPayroll
                        : totals.tenYearPctGdp,
                    displayUnit,
                  )}
                  tone={totals.tenYear >= 0 ? "positive" : "negative"}
                  caption="2026–2035 cumulative"
                  accent
                />
                <MetricTile
                  label="75-year effect"
                  value={formatValue(
                    displayUnit === "dollars"
                      ? totals.total
                      : displayUnit === "pctPayroll"
                        ? totals.totalPctPayroll
                        : totals.totalPctGdp,
                    displayUnit,
                  )}
                  tone={totals.total >= 0 ? "positive" : "negative"}
                  caption="2026–2100 cumulative"
                  accent
                />
                <MetricTile
                  label="2026 baseline TOB"
                  value={
                    baseline2026 ? formatBillions(baseline2026.baselineTobTotal) : "n/a"
                  }
                  caption="Current-law baseline"
                />
                <MetricTile
                  label="OASDI / HI split"
                  value={
                    baseline2026 && baseline2026.baselineTobTotal > 0
                      ? `${Math.round((baseline2026.baselineTobOasdi / baseline2026.baselineTobTotal) * 100)} / ${Math.round((baseline2026.baselineTobMedicareHi / baseline2026.baselineTobTotal) * 100)}`
                      : "n/a"
                  }
                  caption="2026 baseline share"
                />
              </section>

              {/* Chart + inline spotlight */}
              <section className="grid gap-6 2xl:grid-cols-[minmax(0,1.75fr)_minmax(20rem,0.75fr)]">
                <SeriesChart
                  data={visibleData}
                  displayUnit={displayUnit}
                  viewMode={viewMode}
                />

                <div className="overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white">
                  <div className="border-b border-[var(--pe-color-border-light)] px-5 py-3">
                    <h4 className="text-sm font-semibold text-[var(--pe-color-text-title)]">
                      Spotlight years
                    </h4>
                  </div>
                  <table className="min-w-full text-sm">
                    <thead className="text-[var(--pe-color-text-secondary)]">
                      <tr className="border-b border-[var(--pe-color-border-light)]">
                        <th className="px-5 py-2 text-left text-xs font-medium uppercase tracking-wide">
                          Year
                        </th>
                        <th className="px-5 py-2 text-right text-xs font-medium uppercase tracking-wide">
                          Total
                        </th>
                        <th className="px-5 py-2 text-right text-xs font-medium uppercase tracking-wide">
                          OASDI
                        </th>
                        <th className="px-5 py-2 text-right text-xs font-medium uppercase tracking-wide">
                          HI
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--pe-color-border-light)]">
                      {spotlight.map((row) => (
                        <tr key={row.year}>
                          <td className="px-5 py-2.5 font-medium text-[var(--pe-color-text-primary)]">
                            {row.year}
                          </td>
                          <td className="px-5 py-2.5 text-right font-semibold tabular-nums text-[var(--pe-color-text-primary)]">
                            {formatValue(
                              getSeriesValue(row, displayUnit, "total"),
                              displayUnit,
                            )}
                          </td>
                          <td className="px-5 py-2.5 text-right tabular-nums text-[var(--pe-color-primary-700)]">
                            {formatValue(
                              getSeriesValue(row, displayUnit, "oasdi"),
                              displayUnit,
                            )}
                          </td>
                          <td className="px-5 py-2.5 text-right tabular-nums text-[var(--pe-color-text-secondary)]">
                            {formatValue(
                              getSeriesValue(row, displayUnit, "hi"),
                              displayUnit,
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {estimates.length > 0 && (
                    <div className="border-t border-[var(--pe-color-border-light)] bg-[var(--pe-color-bg-secondary)] px-5 py-3">
                      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--pe-color-text-tertiary)]">
                        External comparison
                      </p>
                      <div className="mt-2 space-y-1.5">
                        {estimates.map((estimate) => (
                          <a
                            key={`${estimate.source}-${estimate.budgetWindow}`}
                            href={estimate.url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center justify-between gap-3 text-sm text-[var(--pe-color-text-secondary)] hover:text-[var(--pe-color-primary-700)]"
                          >
                            <span className="truncate">
                              {estimate.source}{" "}
                              <span className="text-[var(--pe-color-text-tertiary)]">
                                · {estimate.budgetWindow}
                              </span>
                            </span>
                            <span className="shrink-0 font-semibold tabular-nums">
                              {formatBillions(estimate.tenYearImpact)}
                            </span>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </section>

              {/* Detailed external comparison table (if present) */}
              <ComparisonTable
                reformId={selectedReform}
                policyEngineEstimate={Math.round(totals.tenYear * 10) / 10}
              />

              <MethodologySection />
            </>
          )}

          <footer className="mt-4 border-t border-[var(--pe-color-border-light)] pt-6 pb-2 text-sm text-[var(--pe-color-text-tertiary)]">
            <p>
              Analysis by{" "}
              <a
                href="https://policyengine.org"
                target="_blank"
                rel="noreferrer"
                className="text-[var(--pe-color-primary-700)] hover:underline"
              >
                PolicyEngine
              </a>
              , commissioned by the Committee for a Responsible Federal Budget. Data:
              2025 Social Security Trustees Report.
            </p>
          </footer>
        </main>
      </motion.div>
    </div>
  );
}
