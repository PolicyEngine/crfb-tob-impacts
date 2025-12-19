import Plot from 'react-plotly.js'
import type { YearlyImpact } from '../types'

interface ImpactChartProps {
  data: YearlyImpact[]
  title: string
  showTrustFundSplit?: boolean
}

const TEAL_500 = '#319795'
const TEAL_300 = '#4FD1C5'
const TEAL_900 = '#1D4044'
const ERROR = '#EF4444'

export function ImpactChart({ data, title, showTrustFundSplit = false }: ImpactChartProps) {
  const years = data.map(d => d.year)

  const traces: Plotly.Data[] = showTrustFundSplit
    ? [
        {
          x: years,
          y: data.map(d => d.tobOasdiImpact),
          type: 'bar' as const,
          name: 'OASDI Trust Fund',
          marker: { color: TEAL_500 },
          hovertemplate: '%{y:$,.1f}B<extra>OASDI</extra>',
        },
        {
          x: years,
          y: data.map(d => d.tobMedicareHiImpact),
          type: 'bar' as const,
          name: 'Medicare HI Trust Fund',
          marker: { color: TEAL_300 },
          hovertemplate: '%{y:$,.1f}B<extra>Medicare HI</extra>',
        },
        {
          x: years,
          y: data.map(d => d.tobOasdiImpact + d.tobMedicareHiImpact),
          type: 'scatter' as const,
          mode: 'lines+markers' as const,
          name: 'Net Total',
          line: { color: TEAL_900, width: 2 },
          marker: { color: TEAL_900, size: 4 },
          hovertemplate: '%{y:$,.1f}B<extra>Net Total</extra>',
        },
      ]
    : [
        {
          x: years,
          y: data.map(d => d.revenueImpact),
          type: 'bar' as const,
          name: 'Revenue Impact',
          marker: {
            color: data.map(d => d.revenueImpact >= 0 ? TEAL_500 : ERROR),
          },
          hovertemplate: '%{y:$,.1f}B<extra></extra>',
        },
      ]

  // Show every 10 years for 75-year view, every year for 10-year view
  const tickInterval = data.length > 20 ? 10 : 1
  const minYear = Math.min(...years)
  const maxYear = Math.max(...years)

  const layout: Partial<Plotly.Layout> = {
    title: { text: title },
    font: { family: 'Inter, sans-serif', size: 14, color: '#344054' },
    xaxis: {
      title: { text: 'Year' },
      tickformat: 'd',
      dtick: tickInterval,
      range: [minYear - 0.5, maxYear + 0.5],
    },
    yaxis: {
      ticksuffix: 'B',
      tickformat: '$,.0f',
    },
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
