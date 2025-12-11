import { useState } from 'react'
import { REFORMS } from '../types'

interface ReformSelectorProps {
  selectedReform: string
  onSelect: (reformId: string) => void
}

export function ReformSelector({ selectedReform, onSelect }: ReformSelectorProps) {
  const [hoveredReform, setHoveredReform] = useState<string | null>(null)

  return (
    <div className="reform-selector">
      <div className="reform-grid">
        {REFORMS.map(reform => (
          <button
            key={reform.id}
            className={`reform-button ${selectedReform === reform.id ? 'selected' : ''}`}
            onClick={() => onSelect(reform.id)}
            onMouseEnter={() => setHoveredReform(reform.id)}
            onMouseLeave={() => setHoveredReform(null)}
            aria-selected={selectedReform === reform.id}
          >
            <span className="reform-number">Option {reform.id.replace('option', '')}</span>
            <span className="reform-name">{reform.shortName}</span>
          </button>
        ))}
      </div>

      <div className="reform-description">
        {(hoveredReform || selectedReform) && (
          <p>
            {REFORMS.find(r => r.id === (hoveredReform || selectedReform))?.description}
          </p>
        )}
      </div>
    </div>
  )
}
