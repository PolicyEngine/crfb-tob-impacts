export function MethodologyDiagram() {
  return (
    <div className="methodology-diagram">
      <svg
        viewBox="0 0 720 320"
        width="720"
        height="320"
        role="img"
        aria-label="Two-stage projection methodology diagram showing economic uprating followed by GREG demographic calibration"
      >
        {/* Background */}
        <rect x="0" y="0" width="720" height="320" fill="#f9fafb" rx="8" />

        {/* Title */}
        <text x="360" y="28" textAnchor="middle" fontSize="16" fontWeight="600" fill="#1f2937">
          Two-Stage Projection Methodology
        </text>

        {/* Divider line */}
        <line x1="360" y1="45" x2="360" y2="310" stroke="#e5e7eb" strokeWidth="2" strokeDasharray="6,4" />

        {/* Stage 1 Header */}
        <text x="180" y="60" textAnchor="middle" fontSize="13" fontWeight="600" fill="#319795">
          STAGE 1: Economic Uprating
        </text>

        {/* Stage 2 Header */}
        <text x="540" y="60" textAnchor="middle" fontSize="13" fontWeight="600" fill="#319795">
          STAGE 2: GREG Calibration
        </text>

        {/* Stage 1 Boxes */}
        {/* Enhanced CPS 2024 */}
        <rect x="80" y="80" width="200" height="50" rx="6" fill="white" stroke="#d1d5db" strokeWidth="1" />
        <text x="180" y="100" textAnchor="middle" fontSize="12" fontWeight="500" fill="#374151">
          Enhanced CPS 2024
        </text>
        <text x="180" y="118" textAnchor="middle" fontSize="10" fill="#6b7280">
          Microdata with ML imputation
        </text>

        {/* Arrow down */}
        <path d="M180 130 L180 148 L175 143 M180 148 L185 143" stroke="#9ca3af" strokeWidth="1.5" fill="none" />

        {/* SSA Trustees Growth Rates */}
        <rect x="80" y="155" width="200" height="50" rx="6" fill="white" stroke="#d1d5db" strokeWidth="1" />
        <text x="180" y="175" textAnchor="middle" fontSize="12" fontWeight="500" fill="#374151">
          SSA Trustees Growth Rates
        </text>
        <text x="180" y="193" textAnchor="middle" fontSize="10" fill="#6b7280">
          AWI, COLA, CPI-U by category
        </text>

        {/* Arrow down */}
        <path d="M180 205 L180 223 L175 218 M180 223 L185 218" stroke="#9ca3af" strokeWidth="1.5" fill="none" />

        {/* Uprated Households */}
        <rect x="80" y="230" width="200" height="50" rx="6" fill="#e6fffa" stroke="#319795" strokeWidth="1.5" />
        <text x="180" y="250" textAnchor="middle" fontSize="12" fontWeight="500" fill="#234e52">
          Uprated Households
        </text>
        <text x="180" y="268" textAnchor="middle" fontSize="10" fill="#285e61">
          Income & parameters → target year
        </text>

        {/* Stage 2 Boxes */}
        {/* Calibration Targets */}
        <rect x="420" y="80" width="200" height="70" rx="6" fill="white" stroke="#d1d5db" strokeWidth="1" />
        <text x="520" y="100" textAnchor="middle" fontSize="12" fontWeight="500" fill="#374151">
          Calibration Targets
        </text>
        <text x="520" y="118" textAnchor="middle" fontSize="10" fill="#6b7280">
          • Age distribution (86 categories)
        </text>
        <text x="520" y="132" textAnchor="middle" fontSize="10" fill="#6b7280">
          • SS benefits • Taxable payroll
        </text>

        {/* Arrow down */}
        <path d="M520 150 L520 168 L515 163 M520 168 L525 163" stroke="#9ca3af" strokeWidth="1.5" fill="none" />

        {/* GREG Calibration */}
        <rect x="420" y="175" width="200" height="50" rx="6" fill="#319795" stroke="#2c7a7b" strokeWidth="1" />
        <text x="520" y="195" textAnchor="middle" fontSize="12" fontWeight="600" fill="white">
          GREG Calibration
        </text>
        <text x="520" y="213" textAnchor="middle" fontSize="10" fill="#e6fffa">
          {"<"}0.1% error on all targets
        </text>

        {/* Arrow down */}
        <path d="M520 225 L520 243 L515 238 M520 243 L525 238" stroke="#9ca3af" strokeWidth="1.5" fill="none" />

        {/* Calibrated Datasets */}
        <rect x="420" y="250" width="200" height="50" rx="6" fill="#e6fffa" stroke="#319795" strokeWidth="1.5" />
        <text x="520" y="270" textAnchor="middle" fontSize="12" fontWeight="500" fill="#234e52">
          Calibrated Datasets
        </text>
        <text x="520" y="288" textAnchor="middle" fontSize="10" fill="#285e61">
          2026–2100 (75 years)
        </text>

        {/* Horizontal arrows connecting stages */}
        {/* Arrow from Stage 1 box to Stage 2 input */}
        <path
          d="M280 255 Q340 255 340 145 Q340 115 420 115"
          stroke="#319795"
          strokeWidth="2"
          fill="none"
          markerEnd="url(#arrowhead)"
        />

        {/* Arrow from Stage 1 bottom to Stage 2 GREG */}
        <path
          d="M280 255 Q350 255 350 200 L420 200"
          stroke="#319795"
          strokeWidth="2"
          fill="none"
          markerEnd="url(#arrowhead)"
        />

        {/* Arrowhead marker */}
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#319795" />
          </marker>
        </defs>
      </svg>
    </div>
  )
}
