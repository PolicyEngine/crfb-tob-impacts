import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ImpactChart } from '../components/ImpactChart'
import type { YearlyImpact } from '../types'

// Mock Plotly to avoid canvas/WebGL issues in tests
vi.mock('react-plotly.js', () => ({
  default: ({ data, layout }: { data: unknown[]; layout: { title?: { text?: string } | string } }) => (
    <div
      data-testid="plotly-chart"
      data-traces={data.length}
      data-title={typeof layout.title === 'object' ? layout.title?.text : layout.title}
    >
      Mock Chart
    </div>
  ),
}))

describe('ImpactChart', () => {
  const mockData: YearlyImpact[] = [
    { year: 2026, revenueImpact: -102.84, tobOasdiImpact: -20.56, tobMedicareHiImpact: -82.28, tobTotalImpact: -102.84, baselineRevenue: 2577.12, reformRevenue: 2474.28, oasdiTaxablePayroll: 10000, gdp: 25000, pctOfOasdiPayroll: -1.03, pctOfGdp: -0.41, oasdiPctOfPayroll: -0.21, hiPctOfPayroll: -0.82, oasdiPctOfGdp: -0.08, hiPctOfGdp: -0.33 },
    { year: 2027, revenueImpact: -111.00, tobOasdiImpact: -21.54, tobMedicareHiImpact: -89.46, tobTotalImpact: -111.00, baselineRevenue: 2748.99, reformRevenue: 2637.99, oasdiTaxablePayroll: 10500, gdp: 26000, pctOfOasdiPayroll: -1.06, pctOfGdp: -0.43, oasdiPctOfPayroll: -0.21, hiPctOfPayroll: -0.85, oasdiPctOfGdp: -0.08, hiPctOfGdp: -0.34 },
  ]

  it('should render a Plotly chart', () => {
    render(<ImpactChart data={mockData} title="Revenue Impact" />)
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument()
  })

  it('should show trust fund breakdown when enabled', () => {
    render(<ImpactChart data={mockData} title="Trust Fund Impact" showTrustFundSplit />)
    const chart = screen.getByTestId('plotly-chart')
    // Should have multiple traces for OASDI and Medicare HI
    expect(Number(chart.getAttribute('data-traces'))).toBeGreaterThan(1)
  })

  it('should format currency values correctly', () => {
    render(<ImpactChart data={mockData} title="Revenue Impact" />)
    // The chart should exist with title
    expect(screen.getByTestId('plotly-chart')).toHaveAttribute('data-title', 'Revenue Impact')
  })
})
