"use client";

import { useEffect, useMemo, useState } from "react";

import {
  loadLiveModelingData,
  type LiveBaselineResult,
  type LiveModelingData,
  type LiveReformStatus,
} from "@/lib/live-modeling-data";

const SPOTLIGHT_YEARS = new Set([2026, 2035, 2050, 2075, 2100]);

function formatNumber(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

function statusClass(status: string): string {
  if (status === "complete" || status === "sentinel_complete") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (status === "failed") {
    return "border-red-200 bg-red-50 text-red-800";
  }
  if (status === "submitted") {
    return "border-blue-200 bg-blue-50 text-blue-800";
  }
  return "border-[var(--pe-color-border-light)] bg-[var(--pe-color-bg-secondary)] text-[var(--pe-color-text-secondary)]";
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

function compactHash(hash: string): string {
  return hash ? `${hash.slice(0, 8)}...` : "";
}

function countByStatus(rows: LiveReformStatus[]): Record<string, number> {
  return rows.reduce<Record<string, number>>((counts, row) => {
    counts[row.reformH5Status] = (counts[row.reformH5Status] ?? 0) + 1;
    return counts;
  }, {});
}

function baselineSpotlightRows(rows: LiveBaselineResult[]): LiveBaselineResult[] {
  return rows.filter((row) => SPOTLIGHT_YEARS.has(row.year));
}

function YearProgress({ rows }: { rows: LiveReformStatus[] }) {
  const byYear = useMemo(() => {
    const groups = new Map<number, LiveReformStatus[]>();
    for (const row of rows) {
      groups.set(row.year, [...(groups.get(row.year) ?? []), row]);
    }
    return [...groups.entries()].sort(([a], [b]) => a - b);
  }, [rows]);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-xs">
        <thead className="text-[var(--pe-color-text-tertiary)]">
          <tr>
            <th className="py-2 pr-4 font-medium">Year</th>
            <th className="py-2 pr-4 font-medium">Complete</th>
            <th className="py-2 pr-4 font-medium">Submitted</th>
            <th className="py-2 pr-4 font-medium">Failed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--pe-color-border-light)]">
          {byYear.map(([year, yearRows]) => {
            const counts = countByStatus(yearRows);
            const complete =
              (counts.complete ?? 0) + (counts.sentinel_complete ?? 0);
            return (
              <tr key={year}>
                <td className="py-2 pr-4 font-medium text-[var(--pe-color-text-title)]">
                  {year}
                </td>
                <td className="py-2 pr-4">{complete}/12</td>
                <td className="py-2 pr-4">{counts.submitted ?? 0}</td>
                <td className="py-2 pr-4">{counts.failed ?? 0}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function LiveModelingProgress() {
  const [data, setData] = useState<LiveModelingData | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    loadLiveModelingData()
      .then((loaded) => {
        if (!cancelled) setData(loaded);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const reformCounts = useMemo(
    () => (data ? countByStatus(data.reformStatus) : {}),
    [data],
  );

  if (error) {
    return (
      <div className="px-5 py-4 text-sm text-red-800">
        Live modeling status failed to load: {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="px-5 py-4 text-sm text-[var(--pe-color-text-secondary)]">
        Loading live modeling status...
      </div>
    );
  }

  const complete =
    (reformCounts.complete ?? 0) + (reformCounts.sentinel_complete ?? 0);
  const submitted = reformCounts.submitted ?? 0;
  const failed = reformCounts.failed ?? 0;
  const pending = reformCounts.pending ?? 0;
  const spotlight = baselineSpotlightRows(data.baseline);

  return (
    <div className="space-y-5 px-5 py-4 text-sm text-[var(--pe-color-text-secondary)]">
      <div className="grid gap-3 sm:grid-cols-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-normal text-[var(--pe-color-text-tertiary)]">
            Baselines
          </p>
          <p className="mt-1 text-lg font-semibold text-[var(--pe-color-text-title)]">
            {data.metadata.baseline_ready_year_count ?? 0}/
            {data.metadata.selected_year_count ?? 0}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-normal text-[var(--pe-color-text-tertiary)]">
            Full H5 complete
          </p>
          <p className="mt-1 text-lg font-semibold text-[var(--pe-color-text-title)]">
            {complete}/{data.metadata.selected_cell_count ?? 0}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-normal text-[var(--pe-color-text-tertiary)]">
            Submitted
          </p>
          <p className="mt-1 text-lg font-semibold text-[var(--pe-color-text-title)]">
            {submitted}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-normal text-[var(--pe-color-text-tertiary)]">
            Failed / pending
          </p>
          <p className="mt-1 text-lg font-semibold text-[var(--pe-color-text-title)]">
            {failed} / {pending}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {Object.entries(reformCounts)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([status, count]) => (
            <span
              key={status}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusClass(status)}`}
            >
              {statusLabel(status)}: {count}
            </span>
          ))}
      </div>

      <div>
        <h4 className="text-sm font-semibold text-[var(--pe-color-text-title)]">
          Baseline spotlight
        </h4>
        <div className="mt-2 overflow-x-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="text-[var(--pe-color-text-tertiary)]">
              <tr>
                <th className="py-2 pr-4 font-medium">Year</th>
                <th className="py-2 pr-4 font-medium">Quality</th>
                <th className="py-2 pr-4 font-medium">TOB total, $B</th>
                <th className="py-2 pr-4 font-medium">OASDI payroll, $B</th>
                <th className="py-2 pr-4 font-medium">ESS</th>
                <th className="py-2 pr-4 font-medium">Support</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--pe-color-border-light)]">
              {spotlight.map((row) => (
                <tr key={row.year}>
                  <td className="py-2 pr-4 font-medium text-[var(--pe-color-text-title)]">
                    {row.year}
                  </td>
                  <td className="py-2 pr-4">{row.calibrationQuality}</td>
                  <td className="py-2 pr-4">{formatNumber(row.h5TobTotalB)}</td>
                  <td className="py-2 pr-4">
                    {formatNumber(row.h5OasdiTaxablePayrollB)}
                  </td>
                  <td className="py-2 pr-4">
                    {formatNumber(row.effectiveSampleSize, 0)}
                  </td>
                  <td className="py-2 pr-4">{row.supportAugmentation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h4 className="text-sm font-semibold text-[var(--pe-color-text-title)]">
          Reform H5 progress by year
        </h4>
        <div className="mt-2">
          <YearProgress rows={data.reformStatus} />
        </div>
      </div>

      <p className="text-xs leading-5 text-[var(--pe-color-text-tertiary)]">
        Generated {data.metadata.generated_at}. Durable full-H5 completion is
        required before a reform cell is treated as production-complete; aggregate
        CSV rows do not qualify. Latest hashes are shown as compact prefixes, for
        example {compactHash(data.reformStatus.find((row) => row.outputH5Sha256)?.outputH5Sha256 ?? "")}.
      </p>
    </div>
  );
}
