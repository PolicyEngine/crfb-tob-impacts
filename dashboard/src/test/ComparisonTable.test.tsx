import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ComparisonTable } from '../components/ComparisonTable'

describe('ComparisonTable', () => {
  it('should render PolicyEngine estimate', () => {
    render(
      <ComparisonTable
        reformId="option1"
        policyEngineEstimate={-1509}
      />
    )

    expect(screen.getByText('PolicyEngine')).toBeInTheDocument()
    expect(screen.getByText('-$1,509B')).toBeInTheDocument()
  })

  it('should render external estimates for option1', () => {
    render(
      <ComparisonTable
        reformId="option1"
        policyEngineEstimate={-1509}
      />
    )

    expect(screen.getByText('CBO')).toBeInTheDocument()
    expect(screen.getByText('-$1,600B')).toBeInTheDocument()
  })

  it('should show message when no external estimates available', () => {
    render(
      <ComparisonTable
        reformId="option2"
        policyEngineEstimate={424}
      />
    )

    expect(screen.getByText(/No external estimates/i)).toBeInTheDocument()
  })

  it('should format positive and negative numbers correctly', () => {
    render(
      <ComparisonTable
        reformId="option7"
        policyEngineEstimate={73}
      />
    )

    expect(screen.getByText('+$73B')).toBeInTheDocument()
  })
})
