export function MethodologyDiagram() {
  return (
    <div className="overflow-x-auto rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-[var(--pe-color-bg-secondary)] px-4 py-4 shadow-[0_12px_28px_rgba(16,24,40,0.05)]">
      <svg
        viewBox="0 0 720 320"
        width="720"
        height="320"
        role="img"
        aria-label="Two-stage projection methodology diagram showing economic uprating followed by positive-entropy demographic and fiscal calibration"
        className="mx-auto h-auto max-w-full"
      >
        <rect x="0" y="0" width="720" height="320" fill="#f9fafb" rx="8" />
        <text x="360" y="28" textAnchor="middle" fontSize="16" fontWeight="600" fill="#1f2937">
          Two-Stage Projection Methodology
        </text>
        <line x1="360" y1="45" x2="360" y2="310" stroke="#e5e7eb" strokeWidth="2" strokeDasharray="6,4" />
        <text x="180" y="60" textAnchor="middle" fontSize="13" fontWeight="600" fill="#319795">
          STAGE 1: Economic Uprating
        </text>
        <text x="540" y="60" textAnchor="middle" fontSize="13" fontWeight="600" fill="#319795">
          STAGE 2: Entropy Calibration
        </text>
        <rect x="80" y="80" width="200" height="50" rx="6" fill="white" stroke="#d1d5db" strokeWidth="1" />
        <text x="180" y="100" textAnchor="middle" fontSize="12" fontWeight="500" fill="#374151">
          Enhanced CPS 2024
        </text>
        <text x="180" y="118" textAnchor="middle" fontSize="10" fill="#6b7280">
          Microdata with ML imputation
        </text>
        <path d="M180 130 L180 148 L175 143 M180 148 L185 143" stroke="#9ca3af" strokeWidth="1.5" fill="none" />
        <rect x="80" y="155" width="200" height="50" rx="6" fill="white" stroke="#d1d5db" strokeWidth="1" />
        <text x="180" y="175" textAnchor="middle" fontSize="12" fontWeight="500" fill="#374151">
          SSA Trustees Growth Rates
        </text>
        <text x="180" y="193" textAnchor="middle" fontSize="10" fill="#6b7280">
          AWI, COLA, CPI-U by category
        </text>
        <path d="M180 205 L180 223 L175 218 M180 223 L185 218" stroke="#9ca3af" strokeWidth="1.5" fill="none" />
        <rect x="80" y="230" width="200" height="50" rx="6" fill="#e6fffa" stroke="#319795" strokeWidth="1.5" />
        <text x="180" y="250" textAnchor="middle" fontSize="12" fontWeight="500" fill="#234e52">
          Uprated Households
        </text>
        <text x="180" y="268" textAnchor="middle" fontSize="10" fill="#285e61">
          Income &amp; parameters → target year
        </text>
        <rect x="420" y="80" width="200" height="90" rx="6" fill="white" stroke="#d1d5db" strokeWidth="1" />
        <text x="520" y="98" textAnchor="middle" fontSize="12" fontWeight="500" fill="#374151">
          5 Calibration Targets
        </text>
        <text x="520" y="114" textAnchor="middle" fontSize="9" fill="#6b7280">
          • Age distribution (86 categories)
        </text>
        <text x="520" y="128" textAnchor="middle" fontSize="9" fill="#6b7280">
          • SS benefits • Taxable payroll
        </text>
        <text x="520" y="142" textAnchor="middle" fontSize="9" fill="#6b7280">
          • OASDI TOB • Medicare HI TOB
        </text>
        <path d="M520 170 L520 188 L515 183 M520 188 L525 183" stroke="#9ca3af" strokeWidth="1.5" fill="none" />
        <rect x="420" y="195" width="200" height="50" rx="6" fill="#319795" stroke="#2c7a7b" strokeWidth="1" />
        <text x="520" y="215" textAnchor="middle" fontSize="12" fontWeight="600" fill="white">
          Entropy Calibration
        </text>
        <text x="520" y="233" textAnchor="middle" fontSize="10" fill="#e6fffa">
          Exact targets, non-negative weights
        </text>
        <path d="M520 245 L520 263 L515 258 M520 263 L525 258" stroke="#9ca3af" strokeWidth="1.5" fill="none" />
        <rect x="420" y="268" width="200" height="42" rx="6" fill="#e6fffa" stroke="#319795" strokeWidth="1.5" />
        <text x="520" y="285" textAnchor="middle" fontSize="12" fontWeight="500" fill="#234e52">
          Calibrated Datasets
        </text>
        <text x="520" y="300" textAnchor="middle" fontSize="10" fill="#285e61">
          2026–2100 (75 years)
        </text>
        <path
          d="M280 255 Q340 255 340 145 Q340 125 420 125"
          stroke="#319795"
          strokeWidth="2"
          fill="none"
          markerEnd="url(#arrowhead)"
        />
        <path
          d="M280 255 Q350 255 350 220 L420 220"
          stroke="#319795"
          strokeWidth="2"
          fill="none"
          markerEnd="url(#arrowhead)"
        />
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#319795" />
          </marker>
        </defs>
      </svg>
    </div>
  );
}
