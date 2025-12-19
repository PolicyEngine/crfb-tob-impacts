import type { DisplayUnit } from '../types'

interface SummaryCardsProps {
  tenYearTotal: number
  seventyFiveYearTotal: number
  scoringType: 'static' | 'dynamic'
  displayUnit: DisplayUnit
  tenYearPctPayroll: number
  tenYearPctGdp: number
  totalPctPayroll: number
  totalPctGdp: number
}

function formatBillions(value: number): string {
  const absValue = Math.abs(value)
  if (absValue >= 1000) {
    return `${(value / 1000).toFixed(1)}T`
  }
  return `${value.toFixed(1)}B`
}

function formatPercentage(value: number): string {
  return `${value.toFixed(2)}%`
}

export function SummaryCards({
  tenYearTotal,
  seventyFiveYearTotal,
  scoringType,
  displayUnit,
  tenYearPctPayroll,
  tenYearPctGdp,
  totalPctPayroll,
  totalPctGdp
}: SummaryCardsProps) {
  const scoringLabel = scoringType === 'static' ? 'Static Scoring' : 'Conventional Scoring'

  // Get display values based on display unit
  let tenYearValue: number
  let seventyFiveYearValue: number
  let formatValue: (v: number) => string
  let prefix: string

  switch (displayUnit) {
    case 'pctPayroll':
      tenYearValue = tenYearPctPayroll
      seventyFiveYearValue = totalPctPayroll
      formatValue = formatPercentage
      prefix = ''
      break
    case 'pctGdp':
      tenYearValue = tenYearPctGdp
      seventyFiveYearValue = totalPctGdp
      formatValue = formatPercentage
      prefix = ''
      break
    default:
      tenYearValue = tenYearTotal
      seventyFiveYearValue = seventyFiveYearTotal
      formatValue = formatBillions
      prefix = '$'
  }

  const isPositive10 = tenYearValue >= 0
  const isPositive75 = seventyFiveYearValue >= 0

  return (
    <div className="summary-cards">
      <div className={`summary-card ${isPositive10 ? 'positive' : 'negative'}`}>
        <span className="card-label">10-Year Impact (2026-2035)</span>
        <span className="card-value">
          {isPositive10 ? '+' : '-'}{prefix}{formatValue(Math.abs(tenYearValue))}
        </span>
        <span className="card-sublabel">{scoringLabel}</span>
      </div>
      <div className={`summary-card ${isPositive75 ? 'positive' : 'negative'}`}>
        <span className="card-label">75-Year Impact (2026-2100)</span>
        <span className="card-value">
          {isPositive75 ? '+' : '-'}{prefix}{formatValue(Math.abs(seventyFiveYearValue))}
        </span>
        <span className="card-sublabel">{scoringLabel}</span>
      </div>
    </div>
  )
}
