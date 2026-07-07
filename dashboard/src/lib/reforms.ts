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

const REFORM_DEFINITIONS: ReformMeta[] = [
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
      "Static and supplemental behavioral results are available for the full 2026-2100 window.",
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
      "Static and supplemental behavioral results are available for the full 2026-2100 window.",
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
      "Static and supplemental behavioral results are available for the full 2026-2100 window.",
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
      "Static and supplemental behavioral results are available for the full 2026-2100 window.",
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
      "Static and supplemental behavioral results are available. Trust-fund allocation follows the explicit OASDI/HI net-impact logic.",
  },
  {
    id: "option6",
    name: "Legacy Short Phase-In Roth Swap",
    shortName: "Short phase-in Roth",
    description:
      "Legacy short phase-in variant retained in raw artifacts but omitted from the CRFB-facing dashboard menu.",
    category: "Employer payroll-tax swap",
    mechanism:
      "Phases in taxation of employer payroll-tax contributions while phasing out benefit taxation over a shorter transition than the publication-facing phased Roth option.",
    baseline:
      "Scored against current law, with transition years comparing a partial payroll-tax inclusion against remaining benefit taxation.",
    interpretation:
      "Use as a raw-data sensitivity rather than a primary publication-facing policy option.",
    scoringNote:
      "Static and supplemental behavioral results are available. Trust-fund allocation follows the explicit OASDI/HI net-impact logic.",
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
      "Dashboard totals show the full federal income-tax gain; OASDI, HI, and general fund lines show where that gain is credited.",
    scoringNote:
      "Static and supplemental behavioral results are available. TOB impacts are calculated from the saved marginal trust-fund revenue columns rather than from the full federal income-tax change.",
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
      "Static and supplemental behavioral results are available for the full 2026-2100 window.",
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
      "Static and supplemental behavioral results are available for the full 2026-2100 window.",
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
      "Static and supplemental behavioral results are available for the full 2026-2100 window.",
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
      "Static and supplemental behavioral results are available for the full 2026-2100 window.",
  },
  {
    id: "option12",
    name: "Phased Roth-Style Swap",
    shortName: "Phased Roth",
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
      "Static and supplemental behavioral results are available. Trust-fund allocation follows the explicit OASDI/HI net-impact logic.",
  },
  {
    id: "reverse_roth",
    name: "Reverse Roth Social Security Proposal",
    shortName: "Reverse Roth",
    description:
      "Tax 100% of Social Security benefits and deduct employee Social Security payroll taxes from income tax.",
    category: "Traditional tax treatment",
    mechanism:
      "Applies full benefit taxation immediately while treating employee OASDI payroll-tax contributions as above-the-line deductions.",
    baseline:
      "Designed to be scored against the same current-law baseline as the standard Social Security benefit-taxation reforms.",
    interpretation:
      "This is the mirror image of a Roth-style Social Security swap: contributions become deductible and benefits become fully taxable.",
    scoringNote:
      "Proposal definition is implemented; dashboard results should be added only after full reform H5 cells have been modeled and aggregated from saved H5 artifacts.",
  },
  {
    id: "tax93",
    name: "Taxation of 93% of Social Security Benefits",
    shortName: "93% taxation",
    description:
      "Tax 93% of Social Security benefits for all recipients, the share Steve Goss's SSA analysis attributed to employer contributions and earnings.",
    category: "Expanded taxation",
    mechanism:
      "Sets every benefit-taxability rate parameter to 93% with thresholds at zero, mirroring the structure of the 90% and 95% options.",
    baseline:
      "Scored against the same current-law baseline as the standard Social Security benefit-taxation reforms.",
    interpretation:
      "Sits between the 90% and 95% options; useful as the Goss-consistent estimate of the taxable share of benefits.",
    scoringNote:
      "Proposal definition is implemented; dashboard results should be added only after full reform H5 cells have been modeled and aggregated from saved H5 artifacts.",
  },
  {
    id: "magi100",
    name: "Full MAGI Inclusion of Benefits",
    shortName: "Full MAGI inclusion",
    description:
      "Count 100% of Social Security benefits, rather than 50%, in the combined income that determines the taxable share of benefits.",
    category: "Expanded taxation",
    mechanism:
      "Raises the IRC section 86(b)(1) combined-income fraction from 50% to 100% of benefits. Benefit-taxation rates, thresholds, and the 85% inclusion cap are unchanged, so benefits become taxable at lower non-benefit incomes and more filers reach the upper tier.",
    baseline:
      "Scored against the same current-law baseline as the standard Social Security benefit-taxation reforms.",
    interpretation:
      "A threshold-side expansion: it broadens who pays and how quickly the taxable share phases in, without changing the maximum taxable share.",
    scoringNote:
      "Scored on the certified full-H5 pipeline at the standard anchor years, with intermediate years interpolated.",
  },
];

// Display order for the sidebar/selector: full repeal, then the 85% family
// (base plus its senior-deduction and credit variants), then the higher
// taxation shares in ascending order, then the Roth-structure options.
const REFORM_DISPLAY_ORDER = [
  "option1",
  "option2",
  "option3",
  "option7",
  "option4",
  "option11",
  "option9",
  "tax93",
  "option10",
  "option8",
  "magi100",
  "option5",
  "option6",
  "option12",
  "reverse_roth",
];

export const REFORMS: ReformMeta[] = [...REFORM_DEFINITIONS].sort(
  (a, b) =>
    REFORM_DISPLAY_ORDER.indexOf(a.id) - REFORM_DISPLAY_ORDER.indexOf(b.id),
);

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
