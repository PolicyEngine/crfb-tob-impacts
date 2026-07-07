"""Build the citable headline summary (10-year and 75-year PV figures).

The dashboard computes present values client-side, which the paper cannot cite
and pytest cannot regression-test. This script reproduces the dashboard's
default view server-side — the default trust-fund split per reform and
per-fund discounting at the Trustees effective interest rates — and writes:

- ``dashboard/public/data/headline_summary.csv`` — one row per
  (baseline_scenario, reform) with the four summary-card figures plus the
  general-fund component, and
- ``paper/exhibits/headline-summary.md`` (mirrored into
  ``paper/sections/exhibits/``) — the citable table for the manuscript.

Solvency rows replicate the dashboard splice: 2026-2034 scored against
scheduled benefits (baseline-share split), 2035-2100 against the solvent
baseline's own split columns.

Inputs are all checked in (results.csv, balanced_fix_results.csv,
effective_interest_rates.csv), so regenerating is deterministic;
tests/test_headline_summary.py fails if the committed outputs go stale.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.trust_fund_allocation import load_allocation_rules  # noqa: E402

DATA = REPO / "dashboard" / "public" / "data"
OUTPUT_CSV = DATA / "headline_summary.csv"
EXHIBIT_DIRS = (REPO / "paper" / "exhibits", REPO / "paper" / "sections" / "exhibits")
SOLVENT_START_YEAR = 2035
TEN_YEAR_END = 2035

# Display order and labels mirror dashboard/src/lib/reforms.ts
# (REFORM_DISPLAY_ORDER); tests assert the two stay in sync.
REFORM_LABELS: dict[str, str] = {
    "option1": "Full repeal",
    "option2": "85% taxation",
    "option3": "85% + deduction",
    "option7": "No senior deduction",
    "option4": "$500 credit",
    "option11": "$700 credit",
    "option9": "90% taxation",
    "tax93": "93% taxation",
    "option10": "95% taxation",
    "option8": "100% taxation",
    "magi100": "Full MAGI inclusion",
    "option5": "Roth swap",
    "option6": "Short phase-in Roth",
    "option12": "Phased Roth",
    "reverse_roth": "Reverse Roth",
}
SOLVENCY_REFORMS = ("option1", "option2", "option8", "option12")


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open() as file:
        return [row for row in csv.DictReader(file)]


def discount_factors() -> tuple[dict[int, float], dict[int, float]]:
    oasdi: dict[int, float] = {}
    hi: dict[int, float] = {}
    oasdi_cumulative = hi_cumulative = 1.0
    for row in sorted(
        _rows(DATA / "effective_interest_rates.csv"), key=lambda r: int(r["year"])
    ):
        year = int(row["year"])
        oasdi_cumulative /= 1 + float(row["oasdi_effective_rate_pct"]) / 100
        hi_cumulative /= 1 + float(row["hi_effective_rate_pct"]) / 100
        oasdi[year] = oasdi_cumulative
        hi[year] = hi_cumulative
    return oasdi, hi


def default_split(row: dict[str, str]) -> tuple[float, float, float, float]:
    """Replicate splitRevenueImpacts at the dashboard's default mode
    ("baselineShares"): returns (revenue, oasdi, hi, general_fund)."""
    rules = load_allocation_rules()
    reform = row["reform_name"]
    value = lambda key: float(row[key])  # noqa: E731

    if reform in rules["directBranchingOptions"] or reform in rules["netImpactOptions"]:
        oasdi = value("oasdi_net_impact")
        hi = value("hi_net_impact")
        return oasdi + hi, oasdi, hi, 0.0
    if reform == "reverse_roth":
        revenue = value("revenue_impact")
        hi = value("tob_medicare_hi_impact")
        return revenue, revenue - hi, hi, 0.0
    revenue = value("revenue_impact")
    if (
        reform in rules["baselineShareOptions"]
        or reform in rules["allocationEligibleOptions"]
    ):
        baseline_total = value("baseline_tob_oasdi") + value("baseline_tob_medicare_hi")
        if baseline_total <= 0:
            return revenue, 0.0, 0.0, revenue
        oasdi = revenue * value("baseline_tob_oasdi") / baseline_total
        return revenue, oasdi, revenue - oasdi, 0.0
    oasdi = value("tob_oasdi_impact")
    hi = value("tob_medicare_hi_impact")
    return revenue, oasdi, hi, revenue - oasdi - hi


def summarize(
    yearly: list[tuple[int, float, float, float, float]],
    factor_oasdi: dict[int, float],
    factor_hi: dict[int, float],
) -> dict[str, float]:
    ten_year = sum(rev for year, rev, *_ in yearly if year <= TEN_YEAR_END)
    pv_oasdi = sum(o * factor_oasdi[year] for year, _, o, _, _ in yearly)
    pv_hi = sum(h * factor_hi[year] for year, _, _, h, _ in yearly)
    pv_general_fund = sum(g * factor_oasdi[year] for year, _, _, _, g in yearly)
    return {
        "ten_year_nominal_billions": ten_year,
        "pv75_total_billions": pv_oasdi + pv_hi + pv_general_fund,
        "pv75_oasdi_billions": pv_oasdi,
        "pv75_medicare_hi_billions": pv_hi,
        "pv75_general_fund_billions": pv_general_fund,
    }


def build() -> list[dict[str, object]]:
    factor_oasdi, factor_hi = discount_factors()
    static = [
        row
        for row in _rows(DATA / "results.csv")
        if row.get("scoring_type") == "static"
    ]
    solvent = [
        row
        for row in _rows(DATA / "balanced_fix_results.csv")
        if row.get("scoring_type") == "static"
        and row.get("baseline_scenario") == "ss_solvent"
    ]

    records: list[dict[str, object]] = []
    for reform in REFORM_LABELS:
        yearly = [
            (int(row["year"]), *default_split(row))
            for row in static
            if row["reform_name"] == reform
        ]
        if not yearly:
            continue
        records.append(
            {
                "baseline_scenario": "scheduled_benefits",
                "reform": reform,
                **summarize(sorted(yearly), factor_oasdi, factor_hi),
            }
        )

    for reform in SOLVENCY_REFORMS:
        spliced = [
            (int(row["year"]), *default_split(row))
            for row in static
            if row["reform_name"] == reform and int(row["year"]) < SOLVENT_START_YEAR
        ]
        for row in solvent:
            if row["reform_name"] != reform:
                continue
            revenue = float(row["revenue_impact"])
            oasdi = float(row["solvent_oasdi_impact"])
            hi = float(row["solvent_medicare_hi_impact"])
            general_fund = float(row["solvent_general_fund_impact"])
            spliced.append((int(row["year"]), revenue, oasdi, hi, general_fund))
        records.append(
            {
                "baseline_scenario": "ss_solvent",
                "reform": reform,
                **summarize(sorted(spliced), factor_oasdi, factor_hi),
            }
        )
    return records


def write_csv(records: list[dict[str, object]]) -> None:
    columns = [
        "baseline_scenario",
        "reform",
        "ten_year_nominal_billions",
        "pv75_total_billions",
        "pv75_oasdi_billions",
        "pv75_medicare_hi_billions",
        "pv75_general_fund_billions",
    ]
    with OUTPUT_CSV.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    key: f"{value:.4f}" if isinstance(value, float) else value
                    for key, value in record.items()
                }
            )


def _fmt(value: float) -> str:
    return f"{value:+,.0f}"


def write_exhibit(records: list[dict[str, object]]) -> None:
    def table(scenario: str) -> str:
        headers = [
            "Reform",
            "10-year (nominal $B)",
            "75-year PV ($B)",
            "OASDI PV ($B)",
            "Medicare HI PV ($B)",
        ]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for record in records:
            if record["baseline_scenario"] != scenario:
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        REFORM_LABELS[str(record["reform"])],
                        _fmt(float(record["ten_year_nominal_billions"])),
                        _fmt(float(record["pv75_total_billions"])),
                        _fmt(float(record["pv75_oasdi_billions"])),
                        _fmt(float(record["pv75_medicare_hi_billions"])),
                    ]
                )
                + " |"
            )
        return "\n".join(lines)

    fragment = "\n".join(
        [
            "Headline revenue effects per reform under the dashboard's default",
            "trust-fund split. Ten-year figures are nominal 2026-2035 sums;",
            "75-year figures discount each fund's 2026-2100 flows at its own",
            "Trustees effective interest rates (OASDI: Table VI.G1 factors;",
            "Medicare HI: Table IV.A4, graded to the 4.7 percent ultimate rate",
            "by 2040), with general-fund flows at the OASDI series. Totals sum",
            "the discounted components; the general-fund component is not",
            "shown separately and is zero under the default split for every",
            "option except the no-senior-deduction option.",
            "",
            "**Scored against scheduled benefits:**",
            "",
            table("scheduled_benefits"),
            "",
            "**Scored against the Social Security solvency baseline (2026-2034",
            "against scheduled benefits, solvent baseline from 2035):**",
            "",
            table("ss_solvent"),
            "",
        ]
    )
    for directory in EXHIBIT_DIRS:
        (directory / "headline-summary.md").write_text(fragment, encoding="utf-8")


def main() -> int:
    records = build()
    write_csv(records)
    write_exhibit(records)
    print(f"wrote {OUTPUT_CSV} ({len(records)} rows) + headline-summary.md exhibits")
    for record in records:
        if record["baseline_scenario"] == "scheduled_benefits":
            print(
                f"  {record['reform']:13} 10yr={record['ten_year_nominal_billions']:9.1f}"
                f"  pv75={record['pv75_total_billions']:9.1f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
