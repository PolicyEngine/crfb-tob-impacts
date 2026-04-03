"use client";

import { EXTERNAL_ESTIMATES } from "@/lib/reforms";

function formatCurrency(value: number) {
  const prefix = value >= 0 ? "+" : "-";
  return `${prefix}$${Math.abs(value).toFixed(1)}B`;
}

export function ComparisonTable({
  reformId,
  policyEngineEstimate,
}: {
  reformId: string;
  policyEngineEstimate: number;
}) {
  const externalEstimates = EXTERNAL_ESTIMATES[reformId] ?? [];

  if (externalEstimates.length === 0) {
    return null;
  }

  return (
    <section className="rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-white px-5 py-5 shadow-[0_18px_48px_rgba(16,24,40,0.06)]">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--pe-color-text-tertiary)]">
          External comparison
        </p>
        <h3 className="mt-2 text-xl font-semibold text-[var(--pe-color-text-title)]">
          Comparison with external estimates
        </h3>
      </div>

      <div className="overflow-x-auto rounded-[var(--pe-radius-container)] border border-[var(--pe-color-border-light)]">
        <table className="min-w-full divide-y divide-[var(--pe-color-border-light)] text-sm">
          <thead className="bg-[var(--pe-color-bg-secondary)] text-left text-[var(--pe-color-text-secondary)]">
            <tr>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Scoring type</th>
              <th className="px-4 py-3 text-right">10-year impact</th>
              <th className="px-4 py-3">Budget window</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--pe-color-border-light)] bg-white">
            <tr className="bg-[var(--pe-color-primary-50)]/60">
              <td className="px-4 py-3 font-semibold text-[var(--pe-color-text-primary)]">
                PolicyEngine
              </td>
              <td className="px-4 py-3 text-[var(--pe-color-text-secondary)]">
                Static
              </td>
              <td className="px-4 py-3 text-right font-semibold text-[var(--pe-color-text-primary)]">
                {formatCurrency(policyEngineEstimate)}
              </td>
              <td className="px-4 py-3 text-[var(--pe-color-text-secondary)]">
                2026-2035
              </td>
            </tr>
            {externalEstimates.map((estimate) => (
              <tr key={`${estimate.source}-${estimate.budgetWindow}`}>
                <td className="px-4 py-3">
                  <a
                    href={estimate.url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-[var(--pe-color-primary-700)] hover:text-[var(--pe-color-primary-800)]"
                  >
                    {estimate.source}
                  </a>
                </td>
                <td className="px-4 py-3 text-[var(--pe-color-text-secondary)]">
                  {estimate.scoringType}
                </td>
                <td className="px-4 py-3 text-right text-[var(--pe-color-text-primary)]">
                  {formatCurrency(estimate.tenYearImpact)}
                </td>
                <td className="px-4 py-3 text-[var(--pe-color-text-secondary)]">
                  {estimate.budgetWindow}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
