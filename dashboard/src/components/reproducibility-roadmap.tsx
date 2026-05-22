import type { LucideIcon } from "lucide-react";
import {
  Boxes,
  CheckCircle2,
  CircleDashed,
  FileCheck2,
  FlaskConical,
  GitBranch,
  PackageCheck,
  PlayCircle,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";

import type {
  RoadmapIcon,
  RoadmapStatus,
} from "@/lib/reproducibility-roadmap-data";
import { reproducibilityRoadmap } from "@/lib/reproducibility-roadmap-data";

const statusConfig: Record<
  RoadmapStatus,
  { label: string; className: string; dotClassName: string }
> = {
  complete: {
    label: "Complete",
    className:
      "border-emerald-200 bg-emerald-50 text-emerald-800",
    dotClassName: "bg-emerald-500",
  },
  gate: {
    label: "Current gate",
    className: "border-amber-200 bg-amber-50 text-amber-900",
    dotClassName: "bg-amber-500",
  },
  planned: {
    label: "Planned",
    className: "border-sky-200 bg-sky-50 text-sky-900",
    dotClassName: "bg-sky-500",
  },
  blocked: {
    label: "Blocked",
    className: "border-rose-200 bg-rose-50 text-rose-900",
    dotClassName: "bg-rose-500",
  },
};

const iconMap: Record<RoadmapIcon, LucideIcon> = {
  package: PackageCheck,
  flask: FlaskConical,
  boxes: Boxes,
  upload: UploadCloud,
  git: GitBranch,
  shield: ShieldCheck,
  play: PlayCircle,
};

function StatusBadge({ status }: { status: RoadmapStatus }) {
  const config = statusConfig[status];

  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${config.className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dotClassName}`} />
      {config.label}
    </span>
  );
}

export function ReproducibilityRoadmap({
  embedded = false,
}: {
  embedded?: boolean;
}) {
  return (
    <section
      aria-labelledby="reproducibility-roadmap-title"
      className={
        embedded
          ? "overflow-hidden bg-white"
          : "overflow-hidden rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white shadow-[0_12px_28px_rgba(16,24,40,0.05)]"
      }
    >
      <div className="border-b border-[var(--pe-color-border-light)] bg-[var(--pe-color-bg-secondary)] px-5 py-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-normal text-[var(--pe-color-primary-700)]">
              Living roadmap
            </p>
            <h3
              id="reproducibility-roadmap-title"
              className="mt-1 text-xl font-semibold tracking-normal text-[var(--pe-color-text-title)]"
            >
              Reproducible production path
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--pe-color-text-secondary)]">
              This is the operating checklist for moving from the latest
              published PolicyEngine stack to verified long-run baseline H5s,
              a policyengine.py bundle, and reform H5 production.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-900">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            Selected panel complete
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-[minmax(0,1.55fr)_minmax(20rem,0.95fr)]">
        <ol className="divide-y divide-[var(--pe-color-border-light)]">
          {reproducibilityRoadmap.steps.map((item) => {
            const Icon = iconMap[item.icon];

            return (
              <li
                key={item.id}
                className="grid gap-4 px-5 py-5 sm:grid-cols-[3.25rem_minmax(0,1fr)]"
              >
                <div className="flex items-start gap-3 sm:block">
                  <div className="grid h-11 w-11 place-items-center rounded-full border border-[var(--pe-color-border-light)] bg-[var(--pe-color-bg-secondary)] text-[var(--pe-color-primary-700)]">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <span className="mt-2 block text-xs font-semibold text-[var(--pe-color-text-tertiary)] sm:text-center">
                    {item.step}
                  </span>
                </div>

                <div className="min-w-0">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <h4 className="text-base font-semibold text-[var(--pe-color-text-title)]">
                      {item.title}
                    </h4>
                    <StatusBadge status={item.status} />
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
                    {item.outcome}
                  </p>

                  <dl className="mt-4 grid gap-3 text-xs leading-5 text-[var(--pe-color-text-secondary)] md:grid-cols-2">
                    <div>
                      <dt className="font-semibold uppercase tracking-normal text-[var(--pe-color-text-tertiary)]">
                        Gate
                      </dt>
                      <dd className="mt-1">{item.gate}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold uppercase tracking-normal text-[var(--pe-color-text-tertiary)]">
                        Log target
                      </dt>
                      <dd className="mt-1 font-mono text-[11px] text-[var(--pe-color-text-title)]">
                        {item.logTarget}
                      </dd>
                    </div>
                  </dl>
                </div>
              </li>
            );
          })}
        </ol>

        <aside className="border-t border-[var(--pe-color-border-light)] bg-[var(--pe-color-bg-secondary)] px-5 py-5 lg:border-l lg:border-t-0">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--pe-color-text-title)]">
              <CircleDashed className="h-4 w-4 text-[var(--pe-color-primary-700)]" />
              Current gate
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
              {reproducibilityRoadmap.currentGate}
            </p>
          </div>

          <div className="mt-6">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--pe-color-text-title)]">
              <FileCheck2 className="h-4 w-4 text-[var(--pe-color-primary-700)]" />
              Review notes
            </div>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--pe-color-text-secondary)]">
              {reproducibilityRoadmap.currentNotes.map((note) => (
                <li key={note} className="flex gap-2">
                  <CheckCircle2
                    className="mt-1 h-4 w-4 shrink-0 text-[var(--pe-color-primary-700)]"
                    aria-hidden="true"
                  />
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-6">
            <div className="text-sm font-semibold text-[var(--pe-color-text-title)]">
              Production flow
            </div>
            <ol className="mt-3 space-y-2">
              {reproducibilityRoadmap.flow.map((label, index) => (
                <li key={label} className="flex items-center gap-3">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-white text-xs font-semibold text-[var(--pe-color-primary-700)] ring-1 ring-[var(--pe-color-border-light)]">
                    {index + 1}
                  </span>
                  <span className="text-sm text-[var(--pe-color-text-secondary)]">
                    {label}
                  </span>
                </li>
              ))}
            </ol>
          </div>

          <div className="mt-6">
            <div className="text-sm font-semibold text-[var(--pe-color-text-title)]">
              Logging ledger
            </div>
            <dl className="mt-3 space-y-3">
              {reproducibilityRoadmap.logTargets.map((item) => (
                <div key={item.label}>
                  <dt className="text-xs font-semibold uppercase tracking-normal text-[var(--pe-color-text-tertiary)]">
                    {item.label}
                  </dt>
                  <dd className="mt-1 break-words font-mono text-[11px] leading-5 text-[var(--pe-color-text-title)]">
                    {item.target}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <p className="mt-6 border-t border-[var(--pe-color-border-light)] pt-4 text-xs text-[var(--pe-color-text-tertiary)]">
            Last updated {reproducibilityRoadmap.lastUpdated}
          </p>
        </aside>
      </div>
    </section>
  );
}
