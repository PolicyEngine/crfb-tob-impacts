import { sitePath } from "@/lib/site-path";

// Net effect of labor-response scoring on total earnings (employment plus
// self-employment, person-weighted) versus the same year's baseline, from
// the corrected behavioral endpoint cells. Built by
// scripts/build_earnings_response.py; endpoint years only (2026 and 2100).
export interface EarningsResponse {
  pct2026: number;
  pct2100: number;
}

const earningsResponseHref = sitePath("/data/earnings_response.csv");

let cached: Promise<Record<string, EarningsResponse>> | null = null;

export function loadEarningsResponses(): Promise<
  Record<string, EarningsResponse>
> {
  cached ??= fetch(earningsResponseHref)
    .then((response) => {
      if (!response.ok) {
        throw new Error(
          `Failed to fetch ${earningsResponseHref}: ${response.status}`,
        );
      }
      return response.text();
    })
    .then((text) => {
      const [header, ...lines] = text.replace(/\r/g, "").trim().split("\n");
      const columns = header.split(",");
      const reformAt = columns.indexOf("reform_name");
      const yearAt = columns.indexOf("year");
      const pctAt = columns.indexOf("pct_change");
      const byReform: Record<string, EarningsResponse> = {};
      for (const line of lines) {
        if (!line) continue;
        const cells = line.split(",");
        const reform = cells[reformAt];
        const year = cells[yearAt];
        const pct = Number(cells[pctAt]);
        const entry = (byReform[reform] ??= { pct2026: NaN, pct2100: NaN });
        if (year === "2026") entry.pct2026 = pct;
        if (year === "2100") entry.pct2100 = pct;
      }
      return byReform;
    });
  return cached;
}
