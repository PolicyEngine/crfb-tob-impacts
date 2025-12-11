import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ReformSelector } from '../components/ReformSelector'
import { REFORMS } from '../types'

describe('ReformSelector', () => {
  it('should render all reform options', () => {
    const onSelect = vi.fn()
    render(<ReformSelector selectedReform="option1" onSelect={onSelect} />)

    REFORMS.forEach(reform => {
      expect(screen.getByText(reform.shortName)).toBeInTheDocument()
    })
  })

  it('should highlight the selected reform', () => {
    const onSelect = vi.fn()
    render(<ReformSelector selectedReform="option2" onSelect={onSelect} />)

    const selectedButton = screen.getByRole('button', { name: /85% Taxation/i })
    expect(selectedButton).toHaveAttribute('aria-selected', 'true')
  })

  it('should call onSelect when a reform is clicked', () => {
    const onSelect = vi.fn()
    render(<ReformSelector selectedReform="option1" onSelect={onSelect} />)

    fireEvent.click(screen.getByText('Full Repeal'))
    expect(onSelect).toHaveBeenCalledWith('option1')
  })

  it('should show reform description on hover/focus', () => {
    const onSelect = vi.fn()
    render(<ReformSelector selectedReform="option1" onSelect={onSelect} />)

    const button = screen.getByText('Full Repeal')
    fireEvent.mouseEnter(button)

    expect(screen.getByText(/Complete elimination/i)).toBeInTheDocument()
  })
})
