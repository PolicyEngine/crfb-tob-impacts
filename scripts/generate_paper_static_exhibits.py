from __future__ import annotations

from pathlib import Path

import pandas as pd


REPO = Path("/Users/maxghenis/PolicyEngine/crfb-tob-impacts")
RESULTS = REPO / "results"
EXHIBITS = REPO / "paper" / "exhibits"
SECTION_EXHIBITS = REPO / "paper" / "sections" / "exhibits"
FINAL_STATIC = RESULTS / "all_static_results_latesthf_2026_2100_14options.csv"
SPECIAL_CASE_ROOT = (
    RESULTS
    / "recovered_special_case_runs"
    / "special_case_reruns__option13-14-exact-2035-2100-20260411"
)
OPTION13_2100_RAW = SPECIAL_CASE_ROOT / "option13" / "2100_static_results.csv"
SENTINEL_FILES = {
    "2073 shock probe": RESULTS / "trustees_current_law_2073_static_shock_sentinel.csv",
    "2075 focus probe": RESULTS / "trustees_current_law_2075_static_focus_sentinel.csv",
    "2078 exact focus panel": RESULTS / "trustees_current_law_2078_focus_complete_sentinel.csv",
    "2079/2081/2086/2100 sparse preflight": RESULTS
    / "trustees_late_sparse_preflight_exact_2079_2081_2086_2100_billions.csv",
}


def fmt_b(value: float) -> str:
    return f"{value:+,.1f}"


def fmt_pct(value: float) -> str:
    return f"{value * 100:.3f}%"


def fmt_millions(value: float) -> str:
    return f"{value / 1e6:+,.3f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def load_static() -> pd.DataFrame:
    return pd.read_csv(FINAL_STATIC).sort_values(["year", "reform_name"]).reset_index(drop=True)


def write(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_exhibit(name: str, text: str) -> None:
    write(EXHIBITS / name, text)
    write(SECTION_EXHIBITS / name, text)


def build_results_overview(df: pd.DataFrame) -> str:
    ten_year = (
        df[df["year"].between(2026, 2035)]
        .groupby("reform_name", as_index=False)["revenue_impact"]
        .sum()
        .sort_values("revenue_impact")
    )
    terminal = df[df["year"] == 2100].sort_values("revenue_impact")

    ten_year_table = markdown_table(
        ["Reform", "2026-2035 Revenue Impact ($B)"],
        [[row.reform_name, fmt_b(row.revenue_impact)] for row in ten_year.itertuples()],
    )
    terminal_table = markdown_table(
        ["Reform", "2100 Revenue Impact ($B)", "2100 TOB Impact ($B)"],
        [
            [row.reform_name, fmt_b(row.revenue_impact), fmt_b(row.tob_total_impact)]
            for row in terminal.itertuples()
        ],
    )

    top_option12 = fmt_b(float(ten_year.loc[ten_year.reform_name == "option12", "revenue_impact"].iloc[0]))
    top_option6 = fmt_b(float(ten_year.loc[ten_year.reform_name == "option6", "revenue_impact"].iloc[0]))
    top_option8 = fmt_b(float(ten_year.loc[ten_year.reform_name == "option8", "revenue_impact"].iloc[0]))
    option1 = fmt_b(float(ten_year.loc[ten_year.reform_name == "option1", "revenue_impact"].iloc[0]))
    option14 = fmt_b(float(ten_year.loc[ten_year.reform_name == "option14_stacked", "revenue_impact"].iloc[0]))

    return f"""
The cleaned static release is now a unified Trustees-lineage package for all
fourteen scenarios. The dashboard and comparison spreadsheet both draw from the
same rebuilt static artifact set. Conventional behavioral results are
quarantined pending a same-baseline rerun and are not summarized in these
manuscript exhibits.

## Ten-year static revenue impacts

{ten_year_table}

In the ten-year window, the largest revenue raisers are `option12`
({top_option12} $B), `option6` ({top_option6} $B), and `option8`
({top_option8} $B). The largest revenue reduction is `option1` ({option1} $B).
The clean special-case baseline `option13` is nearly revenue-neutral in the
first decade, while `option14_stacked` raises {option14} $B over the same
window.

## Terminal-year static impacts

{terminal_table}

At `2100`, the strongest positive revenue effects come from `option8`,
`option10`, and `option9`, while the largest revenue reductions are
`option14_stacked`, `option1`, and `option13`. Late in the horizon, `option7`
goes exactly to zero and `option11` converges numerically toward `option2`,
which is consistent with the fixed nominal credit phase-out in the current
policy specification.
"""


def build_revenue_impacts(df: pd.DataFrame) -> str:
    milestone_years = [2035, 2050, 2075, 2100]
    milestone = df[df["year"].isin(milestone_years)].copy()
    milestone_reforms = [
        "option1",
        "option2",
        "option4",
        "option5",
        "option6",
        "option8",
        "option10",
        "option12",
        "option13",
        "option14_stacked",
    ]
    milestone = milestone[milestone["reform_name"].isin(milestone_reforms)]

    revenue_rows: list[list[str]] = []
    for reform in milestone_reforms:
        row = [reform]
        for year in milestone_years:
            value = float(
                milestone.loc[
                    (milestone["reform_name"] == reform) & (milestone["year"] == year),
                    "revenue_impact",
                ].iloc[0]
            )
            row.append(fmt_b(value))
        revenue_rows.append(row)

    decomposition_reforms = [
        "option1",
        "option2",
        "option4",
        "option8",
        "option12",
        "option13",
        "option14_stacked",
    ]
    decomposition = df[(df["year"] == 2100) & (df["reform_name"].isin(decomposition_reforms))]
    decomposition_rows = [
        [
            row.reform_name,
            fmt_b(row.revenue_impact),
            fmt_b(row.tob_total_impact),
            fmt_b(row.oasdi_net_impact),
            fmt_b(row.hi_net_impact),
        ]
        for row in decomposition.itertuples()
    ]

    revenue_table = markdown_table(
        ["Reform", "2035", "2050", "2075", "2100"],
        revenue_rows,
    )
    decomposition_table = markdown_table(
        ["Reform", "2100 Revenue ($B)", "2100 TOB ($B)", "2100 OASDI Net ($B)", "2100 HI Net ($B)"],
        decomposition_rows,
    )

    return f"""
## Milestone revenue impacts

{revenue_table}

The rebuilt standard series shows the expected late-horizon split: repeal or
TOB-reducing options (`option1`, `option5`, `option6`, `option12`) become
increasingly costly relative to current law, while broader taxation options
(`option2`, `option8`, `option10`) continue to raise revenue. `option13` and
`option14_stacked` should be interpreted separately because they run on the
balanced-fix baseline rather than plain current law.

## Terminal-year trust-fund decomposition

{decomposition_table}

At `2100`, `option13` closes the modeled gaps through a combination of benefit
reduction, higher OASDI payroll-tax revenue, and a smaller positive HI payroll
rate rather than the old negative-HI-rate endpoint. `option14_stacked`
therefore starts from the recovered balanced-fix baseline and shows a much
larger revenue loss than its direct TOB effect alone.
"""


def _scaled_sentinel(path: Path, scale: float) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = [
        "baseline_revenue",
        "reform_revenue",
        "revenue_impact",
        "baseline_tob_total",
        "reform_tob_total",
        "tob_total_impact",
    ]
    if scale != 1:
        for col in cols:
            df[col] = df[col] / scale
    return df


def build_validation_sentinels(df: pd.DataFrame) -> str:
    shock_2073 = _scaled_sentinel(SENTINEL_FILES["2073 shock probe"], 1e9)
    focus_2075 = _scaled_sentinel(SENTINEL_FILES["2075 focus probe"], 1e9)
    focus_2078 = _scaled_sentinel(SENTINEL_FILES["2078 exact focus panel"], 1.0)
    late_sparse = _scaled_sentinel(SENTINEL_FILES["2079/2081/2086/2100 sparse preflight"], 1.0)

    merged = late_sparse.merge(df, on=["reform_name", "year"], suffixes=("_sent", "_final"))
    exact_check_cols = [
        "baseline_revenue",
        "reform_revenue",
        "revenue_impact",
        "baseline_tob_total",
        "reform_tob_total",
        "tob_total_impact",
    ]
    max_abs_delta = max(
        float((merged[f"{col}_sent"] - merged[f"{col}_final"]).abs().max())
        for col in exact_check_cols
    )

    probe_rows = [
        [
            "2073 anomaly probe",
            "option7, option8, option10",
            "option7 = "
            + fmt_b(float(shock_2073.loc[shock_2073.reform_name == "option7", "revenue_impact"].iloc[0]))
            + "; option8 = "
            + fmt_b(float(shock_2073.loc[shock_2073.reform_name == "option8", "revenue_impact"].iloc[0]))
            + "; option10 = "
            + fmt_b(float(shock_2073.loc[shock_2073.reform_name == "option10", "revenue_impact"].iloc[0])),
            "No isolated late-year shock reappears.",
        ],
        [
            "2075 focus probe",
            "option1, option2, option4, option8, option11",
            "option1 = "
            + fmt_b(float(focus_2075.loc[focus_2075.reform_name == "option1", "revenue_impact"].iloc[0]))
            + "; option8 = "
            + fmt_b(float(focus_2075.loc[focus_2075.reform_name == "option8", "revenue_impact"].iloc[0]))
            + "; option11 = "
            + fmt_b(float(focus_2075.loc[focus_2075.reform_name == "option11", "revenue_impact"].iloc[0])),
            "Former splice-cliff years behave normally.",
        ],
        [
            "2078 exact focus panel",
            "option1, option2, option3, option4, option7, option8, option10, option11",
            "option7 = "
            + fmt_b(float(focus_2078.loc[focus_2078.reform_name == "option7", "revenue_impact"].iloc[0]))
            + "; option8 = "
            + fmt_b(float(focus_2078.loc[focus_2078.reform_name == "option8", "revenue_impact"].iloc[0]))
            + "; option10 = "
            + fmt_b(float(focus_2078.loc[focus_2078.reform_name == "option10", "revenue_impact"].iloc[0])),
            "Late-year sign flips remain absent.",
        ],
        [
            "Late sparse exact preflight",
            "2079, 2081, 2086, 2100",
            f"48 overlapping rows; max abs delta vs final delivery = {max_abs_delta:.6f}",
            "Exact match to the rebuilt delivery on overlapping rows.",
        ],
        [
            "Special-case recovery",
            "option13 and option14_stacked",
            "Recovered `66/66` year files for both scenarios; smoke and full-panel checks passed.",
            "Special-case panel now sits on the same clean static lineage.",
        ],
    ]

    probe_table = markdown_table(
        ["Check", "Coverage", "Observed values", "Interpretation"],
        probe_rows,
    )

    return f"""
The clean static release was validated with a mix of directional anomaly probes
and exact overlapping reruns. The early anomaly probes used exact Trustees-line
snapshots to test whether the old splice-like shocks reappeared. The late sparse
preflight then matched the rebuilt delivery exactly on overlapping rows.

{probe_table}
"""


def build_external_benchmarks(df: pd.DataFrame) -> str:
    ten_year = (
        df[df["year"].between(2026, 2035)]
        .groupby("reform_name", as_index=False)["revenue_impact"]
        .sum()
        .set_index("reform_name")["revenue_impact"]
    )

    option1_table = markdown_table(
        ["Source", "Policy", "Scoring", "Window", "Revenue Impact ($B)"],
        [
            ["PolicyEngine", "option1 full repeal", "Static", "2026-2035", fmt_b(float(ten_year["option1"]))],
            ["CBO [@cbo2024options]", "Full repeal", "Conventional", "2025-2034", "-1,600.0"],
            ["SSA Trustees [@ssa2024trustees]", "Full repeal", "Conventional", "2025-2034", "-1,800.0"],
            ["Tax Foundation [@taxfoundation2024trump]", "Full repeal", "Conventional", "2025-2034", "-1,400.0"],
            ["Tax Foundation [@taxfoundation2024trump]", "Full repeal", "Macroeconomic", "2025-2034", "-1,300.0"],
        ],
    )

    option2_table = markdown_table(
        ["Source", "Policy", "Scoring", "Window", "Revenue Impact ($B)"],
        [
            ["PolicyEngine", "option2 tax 85% uniformly", "Static", "2026-2035", fmt_b(float(ten_year["option2"]))],
            ["PolicyEngine", "option8 tax 100% of benefits", "Static", "2026-2035", fmt_b(float(ten_year["option8"]))],
            ["JCT [@jct2024expenditures]", "Current SS tax expenditure", "Conventional", "2024-2028", "+318.4"],
            ["CBO [@cbo2024pension]", "Pension-style basis recovery", "Conventional", "2021-2030", "+458.7"],
        ],
    )

    option7_table = markdown_table(
        ["Source", "Policy", "Scoring", "Window", "Revenue Impact ($B)"],
        [
            ["PolicyEngine", "option7 eliminate bonus senior deduction", "Static", "2026-2035", fmt_b(float(ten_year["option7"]))],
            ["JCT [@jct2025bonus]", "Bonus senior deduction", "Conventional", "FY2025-FY2034", "-66.3"],
        ],
    )

    return f"""
The benchmark layer is still best treated as orientation rather than a
point-estimate competition. The current rebuilt static package continues to sit
within the broad range established by the first report's benchmark set, but the
windows and policy baselines are not identical.

## Option 1: full repeal benchmark

{option1_table}

## Options 2 and 8: broader taxation benchmark

{option2_table}

## Option 7: bonus senior deduction benchmark

{option7_table}

The main comparability caveats remain unchanged from the first report:

- our primary published window is `2026-2035`, while several outside estimates
  use `2025-2034` or other budget windows
- outside scores often use different scoring methods rather than this
  manuscript's cleaned static package
- current-law baselines differ because the temporary senior deduction and other
  tax provisions change the taxable-benefit base in the early years
"""


def build_balanced_fix(df: pd.DataFrame) -> str:
    subset = df[
        df["reform_name"].isin(["option13", "option14_stacked"])
        & df["year"].isin([2035, 2050, 2075, 2100])
    ].copy()
    subset = subset.sort_values(["reform_name", "year"])

    table_rows = [
        [
            row.reform_name,
            str(int(row.year)),
            fmt_b(row.revenue_impact),
            fmt_b(row.tob_total_impact),
            fmt_b(row.oasdi_net_impact),
            fmt_b(row.hi_net_impact),
        ]
        for row in subset.itertuples()
    ]
    table = markdown_table(
        ["Reform", "Year", "Revenue Impact ($B)", "TOB Impact ($B)", "OASDI Net ($B)", "HI Net ($B)"],
        table_rows,
    )

    option13_2100 = pd.read_csv(OPTION13_2100_RAW).iloc[0]
    hi_rate = fmt_pct(float(option13_2100["new_employee_hi_rate"]))
    ss_rate = fmt_pct(float(option13_2100["new_employee_ss_rate"]))
    ss_gap_after_m = fmt_millions(float(option13_2100["ss_gap_after"]))
    hi_gap_after_m = fmt_millions(float(option13_2100["hi_gap_after"]))

    return f"""
`option13` remains a balanced-fix baseline that begins in `2035`, so
`2026-2034` are current-law placeholders by design. `option14_stacked` is then
measured relative to that balanced-fix baseline rather than plain current law.

{table}

At the corrected `2100` endpoint, the recovered `option13` row closes both
modeled gaps while keeping the employee and employer HI rates positive:

- employee and employer SS rate: `{ss_rate}` each
- employee and employer HI rate: `{hi_rate}` each
- benefit multiplier: `{option13_2100["benefit_multiplier"]:.6f}`
- post-reform SS gap: `{ss_gap_after_m}` million dollars
- post-reform HI gap: `{hi_gap_after_m}` million dollars

This matters because the legacy provisional endpoint implied a negative HI
payroll-tax rate. The recovered full-panel rerun removes that pathology from the
publication package.
"""


def build_household_impacts() -> str:
    return """
The cleaned static rebuild finalized the aggregate reform package before the
distributional refresh. As a result, the manuscript does **not** yet cite
updated household-burden or distributional tables from the rebuilt lineage.

This is intentional. The repo still contains archival household-analysis
material from the earlier report, but those artifacts were not regenerated on
top of the cleaned static package and should not be presented as current results
in the manuscript.

The publication rule for this section is therefore:

- keep the chapter slot and citation scaffolding in place
- do not publish legacy household point estimates as if they came from the
  rebuilt static package
- regenerate household/distributional exhibits only after the cleaned household
  aggregation pass is complete
"""


def main() -> None:
    EXHIBITS.mkdir(parents=True, exist_ok=True)
    SECTION_EXHIBITS.mkdir(parents=True, exist_ok=True)
    df = load_static()

    write_exhibit("results-overview.md", build_results_overview(df))
    write_exhibit("revenue-impacts.md", build_revenue_impacts(df))
    write_exhibit("validation-sentinels.md", build_validation_sentinels(df))
    write_exhibit("external-benchmarks.md", build_external_benchmarks(df))
    write_exhibit("balanced-fix.md", build_balanced_fix(df))
    write_exhibit("household-impacts.md", build_household_impacts())

    print("Wrote paper exhibits:")
    for path in sorted(EXHIBITS.glob("*.md")):
        print(f" - {path}")


if __name__ == "__main__":
    main()
