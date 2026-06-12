import { sitePath } from "@/lib/site-path";

export interface TobExplainerPoint {
  other_income: number;
  taxable_amount: number;
  taxable_share: number;
}

export interface TobExplainerCurve {
  filing_status: "SINGLE" | "JOINT";
  ss_benefit: number;
  points: TobExplainerPoint[];
}

export interface TobExplainerContextYear {
  year: number;
  beneficiary_households: number;
  tob_paying_households: number;
  share_of_beneficiary_households_paying: number;
  tob_oasdi_billions: number;
  tob_medicare_hi_billions: number;
}

export interface TobExplainerParameters {
  year: number;
  source: string;
  base_threshold: Record<string, number>;
  adjusted_base_threshold: Record<string, number>;
  base_inclusion_rate: number;
  additional_inclusion_rate: number;
  benefit_inclusion_cap: number;
  combined_income_ss_fraction: number;
}

export interface TobExplainerData {
  schema: string;
  policyengine_us_version: string;
  curve_year: number;
  parameters: TobExplainerParameters;
  curves: TobExplainerCurve[];
  context: TobExplainerContextYear[];
  lineage: Record<string, string>;
}

const explainerHref = sitePath("/data/tob_explainer.json");

export async function loadTobExplainerData(): Promise<TobExplainerData> {
  const response = await fetch(explainerHref);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${explainerHref}: ${response.status}`);
  }
  return (await response.json()) as TobExplainerData;
}
