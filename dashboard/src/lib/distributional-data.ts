import { sitePath } from "@/lib/site-path";

export interface DecileImpact {
  decile: number;
  avg_change: number;
  // null where the decile's aggregate baseline net income is not positive
  // (e.g. the bottom decile), so a percentage change is undefined.
  pct_change: number | null;
  total_change_billions: number;
}

export interface DistributionalData {
  schema: string;
  metric: string;
  anchor_years: number[];
  reforms: string[];
  note: string;
  data: Record<string, Record<string, DecileImpact[]>>;
}

const distributionalHref = sitePath("/data/distributional.json");

export async function loadDistributionalData(): Promise<DistributionalData> {
  const response = await fetch(distributionalHref);
  if (!response.ok) {
    throw new Error(
      `Failed to fetch ${distributionalHref}: ${response.status}`,
    );
  }
  return (await response.json()) as DistributionalData;
}
