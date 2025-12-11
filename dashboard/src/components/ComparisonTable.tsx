import { EXTERNAL_ESTIMATES } from '../types'

interface ComparisonTableProps {
  reformId: string
  policyEngineEstimate: number
}

function formatCurrency(value: number): string {
  const prefix = value >= 0 ? '+' : '-'
  const absValue = Math.abs(value)
  return `${prefix}$${absValue.toLocaleString()}B`
}

export function ComparisonTable({ reformId, policyEngineEstimate }: ComparisonTableProps) {
  const externalEstimates = EXTERNAL_ESTIMATES[reformId] || []

  return (
    <div className="comparison-table">
      <h3>Comparison with External Estimates</h3>
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Scoring Type</th>
            <th>10-Year Impact</th>
            <th>Budget Window</th>
          </tr>
        </thead>
        <tbody>
          <tr className="policyengine-row">
            <td><strong>PolicyEngine</strong></td>
            <td>Static</td>
            <td>{formatCurrency(policyEngineEstimate)}</td>
            <td>2026-2035</td>
          </tr>
          {externalEstimates.length > 0 ? (
            externalEstimates.map((est, idx) => (
              <tr key={idx}>
                <td>{est.source}</td>
                <td>{est.scoringType}</td>
                <td>{formatCurrency(est.tenYearImpact)}</td>
                <td>{est.budgetWindow}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={4} className="no-estimates">
                No external estimates available for comparison
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
