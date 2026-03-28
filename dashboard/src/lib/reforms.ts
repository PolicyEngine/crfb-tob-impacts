export interface ReformMeta {
  id: string;
  name: string;
  shortName: string;
  description: string;
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
  },
  {
    id: "option2",
    name: "Tax 85% of Benefits Uniformly",
    shortName: "85% taxation",
    description:
      "Tax 85% of all Social Security benefits regardless of income level.",
  },
  {
    id: "option3",
    name: "Tax 85% with Bonus Senior Deduction",
    shortName: "85% + deduction",
    description:
      "Apply 85% taxation and permanently extend the bonus senior deduction.",
  },
  {
    id: "option4",
    name: "85% Taxation, Replace Senior Deduction with $500 Credit",
    shortName: "$500 credit",
    description:
      "Keep 85% taxation and replace the bonus senior deduction with a $500 nonrefundable credit.",
  },
  {
    id: "option5",
    name: "Roth-Style Swap (Immediate)",
    shortName: "Roth swap",
    description:
      "Tax employer payroll contributions instead of benefits starting in 2026.",
  },
  {
    id: "option6",
    name: "Phased Roth-Style Swap",
    shortName: "Phased Roth",
    description:
      "Gradually transition from taxing benefits to taxing employer contributions.",
  },
  {
    id: "option7",
    name: "Eliminate Bonus Senior Deduction",
    shortName: "No senior deduction",
    description: "Eliminate the bonus senior deduction.",
  },
  {
    id: "option8",
    name: "Tax 100% of Benefits",
    shortName: "100% taxation",
    description:
      "Tax 100% of all Social Security benefits regardless of income.",
  },
  {
    id: "option9",
    name: "Tax 90% of Benefits",
    shortName: "90% taxation",
    description:
      "Tax 90% of all Social Security benefits regardless of income.",
  },
  {
    id: "option10",
    name: "Tax 95% of Benefits",
    shortName: "95% taxation",
    description:
      "Tax 95% of all Social Security benefits regardless of income.",
  },
  {
    id: "option11",
    name: "85% Taxation, Replace Senior Deduction with $700 Credit",
    shortName: "$700 credit",
    description:
      "Keep 85% taxation and replace the senior deduction with a phased-out $700 nonrefundable credit.",
  },
  {
    id: "option12",
    name: "Extended Roth-Style Swap",
    shortName: "Extended Roth",
    description:
      "Tax employer payroll contributions immediately and phase out benefit taxation from 2029 to 2062.",
  },
  {
    id: "option13",
    name: "Balanced Fix Baseline",
    shortName: "Balanced fix",
    description:
      "Close projected trust fund gaps starting in 2035 using a 50/50 payroll-tax and benefit-cut package.",
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
