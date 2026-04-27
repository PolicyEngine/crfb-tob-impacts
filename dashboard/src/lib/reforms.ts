export interface ReformMeta {
  id: string;
  name: string;
  shortName: string;
  description: string;
  category: string;
  mechanism: string;
  baseline: string;
  interpretation: string;
  scoringNote: string;
}

export interface ExternalEstimate {
  source: string;
  scoringType: string;
  tenYearImpact: number;
  budgetWindow: string;
  url: string;
}

export const REFORMS: ReformMeta[] = [
  {
    id: "option1",
    name: "Full Repeal of Social Security Benefit Taxation",
    shortName: "Full repeal",
    description:
      "Complete elimination of Social Security benefit income taxation starting in 2026.",
    category: "Direct taxability",
    mechanism:
      "Repeals federal income taxation of Social Security benefits beginning in 2026.",
    baseline:
      "Scored against current law, including the temporary senior deduction and its scheduled expiration after 2028.",
    interpretation:
      "Negative values represent lost income-tax revenue currently credited to the OASDI and HI trust funds.",
    scoringNote:
      "Static results are available for the full 2026-2100 window. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option2",
    name: "Tax 85% of Benefits Uniformly",
    shortName: "85% taxation",
    description:
      "Tax 85% of all Social Security benefits regardless of income level.",
    category: "Direct taxability",
    mechanism:
      "Eliminates the current-law income thresholds and applies the top statutory 85 percent inclusion rate to all beneficiaries.",
    baseline:
      "Scored against current-law benefit taxation rules, where taxable benefits phase in only above combined-income thresholds.",
    interpretation:
      "Positive values show the added revenue from expanding the taxable-benefit base below the current thresholds.",
    scoringNote:
      "Static results are available for the full 2026-2100 window. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option3",
    name: "Tax 85% with Bonus Senior Deduction",
    shortName: "85% + deduction",
    description:
      "Apply 85% taxation and permanently extend the bonus senior deduction.",
    category: "Senior relief",
    mechanism:
      "Combines uniform 85 percent benefit taxation with permanent extension of the temporary bonus senior deduction.",
    baseline:
      "The baseline senior deduction expires after 2028; this reform keeps that relief in place indefinitely.",
    interpretation:
      "Results combine added taxable-benefit revenue with the offsetting cost of extending the senior deduction.",
    scoringNote:
      "Static results are available for the full 2026-2100 window. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option4",
    name: "85% Taxation, Replace Senior Deduction with $500 Credit",
    shortName: "$500 credit",
    description:
      "Keep 85% taxation and replace the bonus senior deduction with a $500 nonrefundable credit.",
    category: "Senior relief",
    mechanism:
      "Applies uniform 85 percent benefit taxation, repeals the bonus senior deduction, and creates a $500 nonrefundable credit tied to Social Security tax liability.",
    baseline:
      "Scored against current law with the temporary senior deduction still present through 2028.",
    interpretation:
      "The credit targets relief more directly than a deduction, so revenue effects reflect both the broader tax base and the capped credit offset.",
    scoringNote:
      "Static results are available for the full 2026-2100 window. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option5",
    name: "Roth-Style Swap (Immediate)",
    shortName: "Roth swap",
    description:
      "Tax employer payroll contributions instead of benefits starting in 2026.",
    category: "Employer payroll-tax swap",
    mechanism:
      "Eliminates Social Security benefit taxation and instead treats employer payroll-tax contributions as taxable compensation.",
    baseline:
      "Scored against current-law benefit taxation and payroll-tax treatment.",
    interpretation:
      "This is a structural tax-base shift from retirees toward workers, not just a change in taxable-benefit inclusion.",
    scoringNote:
      "Static results are available; trust-fund allocation follows the explicit OASDI/HI net-impact logic. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option6",
    name: "Phased Roth-Style Swap",
    shortName: "Phased Roth",
    description:
      "Gradually transition from taxing benefits to taxing employer contributions.",
    category: "Employer payroll-tax swap",
    mechanism:
      "Phases in taxation of employer payroll-tax contributions while phasing out benefit taxation over time.",
    baseline:
      "Scored against current law, with transition years comparing a partial payroll-tax inclusion against remaining benefit taxation.",
    interpretation:
      "The time path matters: early years show the phase-in, while later years converge toward the structural swap.",
    scoringNote:
      "Static results are available; trust-fund allocation follows the explicit OASDI/HI net-impact logic. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option7",
    name: "Eliminate Bonus Senior Deduction",
    shortName: "No senior deduction",
    description: "Eliminate the bonus senior deduction.",
    category: "Senior relief",
    mechanism:
      "Repeals the temporary bonus senior deduction without otherwise changing Social Security benefit-taxation rules.",
    baseline:
      "The baseline deduction is temporary and expires after 2028, so this option mainly affects 2026-2028.",
    interpretation:
      "Positive values represent higher income-tax revenue from removing the temporary deduction.",
    scoringNote:
      "Static results are available; this is treated as a general-revenue change rather than a direct OASDI/HI benefit-tax split. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option8",
    name: "Tax 100% of Benefits",
    shortName: "100% taxation",
    description:
      "Tax 100% of all Social Security benefits regardless of income.",
    category: "Direct taxability",
    mechanism:
      "Eliminates thresholds and includes all Social Security benefits in taxable income.",
    baseline:
      "Scored against current-law thresholds and the current maximum 85 percent taxable-benefit inclusion rate.",
    interpretation:
      "This is the broadest direct benefit-taxation option, so positive revenue effects are larger than under 85, 90, or 95 percent inclusion.",
    scoringNote:
      "Static results are available for the full 2026-2100 window. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option9",
    name: "Tax 90% of Benefits",
    shortName: "90% taxation",
    description:
      "Tax 90% of all Social Security benefits regardless of income.",
    category: "Direct taxability",
    mechanism:
      "Eliminates thresholds and includes 90 percent of every beneficiary's Social Security benefits in taxable income.",
    baseline:
      "Scored against current-law thresholds and the current maximum 85 percent taxable-benefit inclusion rate.",
    interpretation:
      "Revenue effects sit between uniform 85 percent taxation and broader 95 or 100 percent inclusion.",
    scoringNote:
      "Static results are available for the full 2026-2100 window. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option10",
    name: "Tax 95% of Benefits",
    shortName: "95% taxation",
    description:
      "Tax 95% of all Social Security benefits regardless of income.",
    category: "Direct taxability",
    mechanism:
      "Eliminates thresholds and includes 95 percent of every beneficiary's Social Security benefits in taxable income.",
    baseline:
      "Scored against current-law thresholds and the current maximum 85 percent taxable-benefit inclusion rate.",
    interpretation:
      "Revenue effects are larger than under 85 or 90 percent inclusion but smaller than taxing all benefits.",
    scoringNote:
      "Static results are available for the full 2026-2100 window. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option11",
    name: "85% Taxation, Replace Senior Deduction with $700 Credit",
    shortName: "$700 credit",
    description:
      "Keep 85% taxation and replace the senior deduction with a phased-out $700 nonrefundable credit.",
    category: "Senior relief",
    mechanism:
      "Applies uniform 85 percent benefit taxation, repeals the bonus senior deduction, and creates a phased-out $700 nonrefundable Social Security credit.",
    baseline:
      "Scored against current law with the temporary senior deduction through 2028 and no permanent replacement credit.",
    interpretation:
      "The larger credit provides more offset than the $500 design and phases out above higher incomes.",
    scoringNote:
      "Static results are available for the full 2026-2100 window. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option12",
    name: "Extended Roth-Style Swap",
    shortName: "Extended Roth",
    description:
      "Tax employer payroll contributions immediately and phase out benefit taxation from 2029 to 2062.",
    category: "Employer payroll-tax swap",
    mechanism:
      "Taxes employer payroll-tax contributions immediately while phasing out benefit taxation over an extended schedule.",
    baseline:
      "Scored against current law, with the OASDI share of benefit taxation phased out before the HI share.",
    interpretation:
      "The late-horizon sign can differ from the first decade because the payroll-tax inclusion and benefit-tax phaseout operate on different bases.",
    scoringNote:
      "Static results are available; trust-fund allocation follows the explicit OASDI/HI net-impact logic. Conventional results are quarantined pending a same-baseline rerun.",
  },
  {
    id: "option13",
    name: "Balanced Fix Baseline",
    shortName: "Balanced fix",
    description:
      "Close projected trust fund gaps starting in 2035 using a 50/50 payroll-tax and benefit-cut package.",
    category: "Special case",
    mechanism:
      "Combines proportional Social Security benefit reductions with Social Security and Medicare payroll-tax increases beginning in 2035.",
    baseline:
      "This is a stylized solvency baseline, not a standard reform scored against current law.",
    interpretation:
      "Read the dedicated Balanced Fix tab rather than comparing it directly with Options 1-12.",
    scoringNote:
      "Only static special-case results are included in the public release.",
  },
  {
    id: "option14_stacked",
    name: "Extended Roth-Style Swap Relative to Balanced Fix",
    shortName: "Stacked Roth",
    description:
      "Apply the extended employer-payroll-tax swap on top of the balanced-fix baseline.",
    category: "Special case",
    mechanism:
      "Uses the Option 13 balanced-fix reform as the baseline, then layers the Option 12 structural swap on top.",
    baseline:
      "Unlike Options 1-12, this is not a current-law comparison; it measures the incremental structural swap effect relative to the balanced-fix baseline.",
    interpretation:
      "Read as the additional effect of the structural swap after the solvency baseline, not as a standalone current-law reform.",
    scoringNote:
      "Only static special-case results are included in the public release.",
  },
];

export const EXTERNAL_ESTIMATES: Record<string, ExternalEstimate[]> = {
  option1: [
    {
      source: "CBO",
      scoringType: "Conventional",
      tenYearImpact: -1600,
      budgetWindow: "2025-2034",
      url: "https://www.cbo.gov/budget-options/56856",
    },
    {
      source: "Tax Foundation",
      scoringType: "Conventional",
      tenYearImpact: -1400,
      budgetWindow: "2025-2034",
      url: "https://taxfoundation.org/blog/trump-social-security-tax/",
    },
  ],
  option7: [
    {
      source: "JCT",
      scoringType: "Conventional",
      tenYearImpact: 66.3,
      budgetWindow: "2025-2034",
      url: "https://www.jct.gov/publications/2025/jcx-26-25r/",
    },
  ],
};
