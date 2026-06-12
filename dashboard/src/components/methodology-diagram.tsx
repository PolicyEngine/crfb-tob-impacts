const palette = {
  text: "#1f2937",
  subtext: "#6b7280",
  border: "#d1d5db",
  teal: "#319795",
  tealDark: "#234e52",
  tealDeep: "#2c7a7b",
  tealWash: "#e6fffa",
  amber: "#b45309",
  amberWash: "#fffbeb",
  amberBorder: "#f59e0b",
};

function Box({
  x,
  y,
  w,
  h,
  title,
  caption,
  caption2,
  accent = false,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  caption?: string;
  caption2?: string;
  accent?: boolean;
}) {
  const cx = x + w / 2;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={6}
        fill={accent ? palette.tealWash : "white"}
        stroke={accent ? palette.teal : palette.border}
        strokeWidth={accent ? 1.5 : 1}
      />
      <text
        x={cx}
        y={y + 19}
        textAnchor="middle"
        fontSize="12"
        fontWeight="600"
        fill={accent ? palette.tealDark : palette.text}
      >
        {title}
      </text>
      {caption ? (
        <text x={cx} y={y + 35} textAnchor="middle" fontSize="9.5" fill={palette.subtext}>
          {caption}
        </text>
      ) : null}
      {caption2 ? (
        <text x={cx} y={y + 48} textAnchor="middle" fontSize="9.5" fill={palette.subtext}>
          {caption2}
        </text>
      ) : null}
    </g>
  );
}

function Down({ x, y1, y2 }: { x: number; y1: number; y2: number }) {
  return (
    <path
      d={`M${x} ${y1} L${x} ${y2}`}
      stroke={palette.teal}
      strokeWidth="2"
      fill="none"
      markerEnd="url(#md-arrow)"
    />
  );
}

export function MethodologyDiagram() {
  return (
    <div className="overflow-x-auto rounded-[var(--pe-radius-feature)] border border-[var(--pe-color-border-light)] bg-[var(--pe-color-bg-secondary)] px-4 py-4 shadow-[0_12px_28px_rgba(16,24,40,0.05)]">
      <svg
        viewBox="0 0 760 600"
        width="760"
        height="600"
        role="img"
        aria-label="Baseline construction pipeline: populace microdata and Trustees, Medicare, and CBO targets feed yearly demographic reweighting, value calibration, and a final entropy calibration with publication gates, producing 2026 to 2100 datasets for the reform panel"
        className="mx-auto h-auto max-w-full"
      >
        <rect x="0" y="0" width="760" height="600" fill="#f9fafb" rx="8" />
        <text x="380" y="26" textAnchor="middle" fontSize="16" fontWeight="600" fill={palette.text}>
          How each projection year is built
        </text>
        <text x="380" y="44" textAnchor="middle" fontSize="10.5" fill={palette.subtext}>
          Demographics enter through weights; economics enter through values. Every year from 2026
          to 2100 is calibrated independently.
        </text>

        {/* Inputs row */}
        <Box
          x={20}
          y={62}
          w={170}
          h={56}
          title="populace 2024"
          caption="Primary-source microdata"
          caption2="(ASEC, PUF, SCF, SIPP, MEPS)"
        />
        <Box
          x={205}
          y={62}
          w={170}
          h={56}
          title="2026 Trustees Report"
          caption="Age distribution, payroll,"
          caption2="OASDI cost, TOB, GDP, AWI"
        />
        <Box
          x={390}
          y={62}
          w={170}
          h={56}
          title="CMS 2026 tables"
          caption="Medicare HI taxation-of-"
          caption2="benefits income, annual"
        />
        <Box
          x={575}
          y={62}
          w={165}
          h={56}
          title="CBO long-run forecast"
          caption="Per-category income growth"
          caption2="through 2034"
        />

        {/* arrows from inputs into the pipeline */}
        <path
          d="M105 118 L105 136 Q105 146 115 146 L260 146"
          stroke={palette.teal}
          strokeWidth="2"
          fill="none"
        />
        <path
          d="M290 118 L290 132"
          stroke={palette.teal}
          strokeWidth="2"
          fill="none"
          markerEnd="url(#md-arrow)"
        />
        <path
          d="M475 118 L475 136 Q475 146 465 146 L420 146"
          stroke={palette.teal}
          strokeWidth="2"
          fill="none"
        />
        <path
          d="M657 118 L657 136 Q657 146 647 146 L420 146"
          stroke={palette.teal}
          strokeWidth="2"
          fill="none"
          markerEnd="url(#md-arrow)"
        />

        {/* Stage A */}
        <Box
          x={120}
          y={140}
          w={340}
          h={58}
          title="A. Grow incomes to the target year"
          caption="Model uprating by category, CBO-vintage through 2034; capped at"
          caption2="Trustees nominal GDP growth beyond so no source outruns the economy"
        />
        <Down x={290} y1={198} y2={214} />

        {/* Stage B */}
        <Box
          x={120}
          y={218}
          w={340}
          h={50}
          title="B. Demographic reweight (light entropy)"
          caption="Shift household weights to the Trustees single-year age distribution"
        />
        <Down x={290} y1={268} y2={284} />

        {/* Stage C */}
        <Box
          x={120}
          y={288}
          w={340}
          h={70}
          title="C. Value calibration, given those weights"
          caption="α scales earnings to SSA taxable payroll (taxable-max aware) · β scales"
          caption2="benefits to OASDI cost · γ nudges beneficiary other income toward TOB"
        />
        <Down x={290} y1={358} y2={374} />

        {/* support augmentation callout */}
        <g>
          <rect
            x={490}
            y={288}
            width={250}
            height={70}
            rx={6}
            fill={palette.amberWash}
            stroke={palette.amberBorder}
            strokeWidth={1}
          />
          <text x={615} y={307} textAnchor="middle" fontSize="11" fontWeight="600" fill={palette.amber}>
            2075+ support augmentation
          </text>
          <text x={615} y={323} textAnchor="middle" fontSize="9.5" fill={palette.subtext}>
            Jittered resamples of real households
          </text>
          <text x={615} y={336} textAnchor="middle" fontSize="9.5" fill={palette.subtext}>
            spread weight across the much older
          </text>
          <text x={615} y={349} textAnchor="middle" fontSize="9.5" fill={palette.subtext}>
            age mix; totals re-pinned to targets
          </text>
          <path
            d="M490 323 L460 323"
            stroke={palette.amberBorder}
            strokeWidth="1.5"
            fill="none"
          />
        </g>

        {/* Stage D */}
        <Box
          x={120}
          y={378}
          w={340}
          h={58}
          title="D. Final entropy calibration"
          caption="Exact targets: age distribution, benefits, payroll, OASDI and HI TOB,"
          caption2="plus guards holding investment and other income to their growth paths"
        />
        <Down x={290} y1={436} y2={452} />

        {/* Gates */}
        <g>
          <rect x={120} y={456} width={340} height={44} rx={6} fill={palette.teal} stroke={palette.tealDeep} />
          <text x={290} y={474} textAnchor="middle" fontSize="12" fontWeight="600" fill="white">
            Publication gates
          </text>
          <text x={290} y={490} textAnchor="middle" fontSize="9.5" fill={palette.tealWash}>
            Effective sample size, weight concentration, and TOB contributor support
          </text>
        </g>
        <Down x={290} y1={500} y2={516} />

        {/* Output */}
        <Box
          x={120}
          y={520}
          w={340}
          h={56}
          title="Calibrated year datasets, 2026–2100"
          caption="Each year feeds the reform panel: 14 options simulated on Modal with"
          caption2="full-output audit artifacts behind every published number"
          accent
        />

        {/* side note: independence */}
        <text x={615} y={460} textAnchor="middle" fontSize="9.5" fill={palette.subtext}>
          Failing any gate blocks publication
        </text>
        <text x={615} y={473} textAnchor="middle" fontSize="9.5" fill={palette.subtext}>
          for that year; diagnostics for every
        </text>
        <text x={615} y={486} textAnchor="middle" fontSize="9.5" fill={palette.subtext}>
          series appear in the baseline section.
        </text>

        <defs>
          <marker id="md-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill={palette.teal} />
          </marker>
        </defs>
      </svg>
    </div>
  );
}
