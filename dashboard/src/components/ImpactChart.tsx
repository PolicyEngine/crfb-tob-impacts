import Plot from 'react-plotly.js'
import type { YearlyImpact, DisplayUnit } from '../types'

interface ImpactChartProps {
  data: YearlyImpact[]
  title: string
  showTrustFundSplit?: boolean
  displayUnit?: DisplayUnit
}

const TEAL_500 = '#319795'
const TEAL_300 = '#4FD1C5'
const TEAL_900 = '#1D4044'

export function ImpactChart({ data, title, showTrustFundSplit = false, displayUnit = 'dollars' }: ImpactChartProps) {
  const years = data.map(d => d.year)

  // Get values based on display unit
  const getOasdiValue = (d: YearlyImpact) => {
    switch (displayUnit) {
      case 'pctPayroll': return d.oasdiPctOfPayroll
      case 'pctGdp': return d.oasdiPctOfGdp
      default: return d.tobOasdiImpact
    }
  }

  const getHiValue = (d: YearlyImpact) => {
    switch (displayUnit) {
      case 'pctPayroll': return d.hiPctOfPayroll
      case 'pctGdp': return d.hiPctOfGdp
      default: return d.tobMedicareHiImpact
    }
  }

  const getTotalValue = (d: YearlyImpact) => {
    switch (displayUnit) {
      case 'pctPayroll': return d.pctOfOasdiPayroll
      case 'pctGdp': return d.pctOfGdp
      default: return d.tobOasdiImpact + d.tobMedicareHiImpact
    }
  }

  // Format strings for hover based on display unit
  const hoverFormat = displayUnit === 'dollars' ? '%{y:$,.1f}B' : '%{y:.2f}%'

  const traces: Plotly.Data[] = showTrustFundSplit
    ? [
        {
          x: years,
          y: data.map(getOasdiValue),
          type: 'bar' as const,
          name: 'OASDI Trust Fund',
          marker: { color: TEAL_500 },
          hovertemplate: `${hoverFormat}<extra>OASDI</extra>`,
        },
        {
          x: years,
          y: data.map(getHiValue),
          type: 'bar' as const,
          name: 'Medicare HI Trust Fund',
          marker: { color: TEAL_300 },
          hovertemplate: `${hoverFormat}<extra>Medicare HI</extra>`,
        },
        {
          x: years,
          y: data.map(getTotalValue),
          type: 'scatter' as const,
          mode: 'lines+markers' as const,
          name: 'Net Total',
          line: { color: TEAL_900, width: 2 },
          marker: { color: TEAL_900, size: 4 },
          hovertemplate: `${hoverFormat}<extra>Net Total</extra>`,
        },
      ]
    : [
        {
          x: years,
          y: data.map(getTotalValue),
          type: 'bar' as const,
          name: 'Revenue Impact',
          marker: {
            color: data.map(d => getTotalValue(d) >= 0 ? TEAL_500 : '#EF4444'),
          },
          hovertemplate: `${hoverFormat}<extra></extra>`,
        },
      ]

  // Show every 10 years for 75-year view, every year for 10-year view
  const tickInterval = data.length > 20 ? 10 : 1
  const minYear = Math.min(...years)
  const maxYear = Math.max(...years)

  // Calculate y-axis range for consistent scaling
  const allValues = showTrustFundSplit
    ? [...data.map(getOasdiValue), ...data.map(getHiValue), ...data.map(getTotalValue)]
    : data.map(getTotalValue)

  const minValue = Math.min(...allValues)
  const maxValue = Math.max(...allValues)
  const hasNegative = minValue < 0
  const hasPositive = maxValue > 0

  // Calculate nice rounded range for percentages
  const getNiceRange = (min: number, max: number): [number, number] => {
    if (displayUnit === 'dollars') {
      // For dollars, let Plotly auto-scale but ensure 0 is included
      if (hasNegative && hasPositive) {
        const absMax = Math.max(Math.abs(min), Math.abs(max))
        return [-absMax * 1.1, absMax * 1.1]
      } else if (hasNegative) {
        return [min * 1.1, 0]
      } else {
        return [0, max * 1.1]
      }
    }

    // For percentages, round to nice values
    const absMax = Math.max(Math.abs(min), Math.abs(max))
    // Round up to nearest 0.5%
    const niceMax = Math.ceil(absMax * 2) / 2

    if (hasNegative && hasPositive) {
      return [-niceMax, niceMax]
    } else if (hasNegative) {
      return [-niceMax, 0]
    } else {
      return [0, niceMax]
    }
  }

  const [yMin, yMax] = getNiceRange(minValue, maxValue)

  // Y-axis formatting based on display unit
  const yaxisConfig = displayUnit === 'dollars'
    ? {
        ticksuffix: 'B',
        tickformat: '$,.0f',
        range: [yMin, yMax],
      }
    : {
        ticksuffix: '%',
        tickformat: '.2f',
        range: [yMin, yMax],
      }

  const layout: Partial<Plotly.Layout> = {
    title: { text: title },
    font: { family: 'Inter, sans-serif', size: 14, color: '#344054' },
    xaxis: {
      title: { text: 'Year' },
      tickformat: 'd',
      dtick: tickInterval,
      range: [minYear - 0.5, maxYear + 0.5],
    },
    yaxis: yaxisConfig,
    barmode: 'relative',
    showlegend: showTrustFundSplit,
    legend: { orientation: 'h', y: -0.25, x: 0.5, xanchor: 'center' },
    margin: { l: 80, r: 40, t: 60, b: 100 },
    plot_bgcolor: '#fff',
    paper_bgcolor: '#fff',
    images: [
      {
        source: 'https://raw.githubusercontent.com/PolicyEngine/policyengine-app/master/src/images/logos/policyengine/teal.png',
        xref: 'paper',
        yref: 'paper',
        x: 1,
        y: -0.15,
        sizex: 0.1,
        sizey: 0.1,
        xanchor: 'right',
        yanchor: 'bottom',
      },
    ],
  }

  return (
    <div className="chart-container">
      <Plot
        data={traces}
        layout={layout}
        useResizeHandler
        style={{ width: '100%', height: '400px' }}
        config={{ displayModeBar: false, responsive: true }}
      />
    </div>
  )
}
