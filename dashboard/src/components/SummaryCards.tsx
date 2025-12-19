interface SummaryCardsProps {
  tenYearTotal: number
  seventyFiveYearTotal: number
  scoringType: 'static' | 'dynamic'
}

function formatBillions(value: number): string {
  const absValue = Math.abs(value)
  if (absValue >= 1000) {
    return `${(value / 1000).toFixed(1)}T`
  }
  return `${value.toFixed(1)}B`
}

export function SummaryCards({ tenYearTotal, seventyFiveYearTotal, scoringType }: SummaryCardsProps) {
  const isPositive10 = tenYearTotal >= 0
  const isPositive75 = seventyFiveYearTotal >= 0
  const scoringLabel = scoringType === 'static' ? 'Static Scoring' : 'Conventional Scoring'

  return (
    <div className="summary-cards">
      <div className={`summary-card ${isPositive10 ? 'positive' : 'negative'}`}>
        <span className="card-label">10-Year Impact (2026-2035)</span>
        <span className="card-value">
          {isPositive10 ? '+' : '-'}${formatBillions(Math.abs(tenYearTotal))}
        </span>
        <span className="card-sublabel">{scoringLabel}</span>
      </div>
      <div className={`summary-card ${isPositive75 ? 'positive' : 'negative'}`}>
        <span className="card-label">75-Year Impact (2026-2100)</span>
        <span className="card-value">
          {isPositive75 ? '+' : '-'}${formatBillions(Math.abs(seventyFiveYearTotal))}
        </span>
        <span className="card-sublabel">{scoringLabel}</span>
      </div>
    </div>
  )
}
