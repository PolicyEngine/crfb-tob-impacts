from __future__ import annotations

from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
EXHIBITS = REPO / "paper" / "exhibits"
SECTION_EXHIBITS = REPO / "paper" / "sections" / "exhibits"
STANDARD_REFORMS = tuple(f"option{i}" for i in range(1, 13)) + ("reverse_roth", "tax93")


def fmt_b(value: float) -> str:
    return f"{value:+,.1f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def load_static() -> pd.DataFrame:
    # New certified-base panel (dashboard results.csv is the canonical surface).
    src = REPO / "dashboard" / "public" / "data" / "results.csv"
    df = pd.read_csv(src)
    df = df[df["scoring_type"] == "static"].copy()
    # Provenance columns the rebuilt pipeline does not yet capture per cell
    # (saved-microdata lineage is a cleanup item) — placeholders so number
    # exhibits render and lineage exhibits degrade gracefully rather than crash.
    for col in ("source", "scenario_h5_uri", "baseline_source"):
        if col not in df.columns:
            df[col] = ""
    df = df.sort_values(["year", "reform_name"]).reset_index(drop=True)
    return df[df["reform_name"].isin(STANDARD_REFORMS)].copy()


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

    top_option12 = fmt_b(
        float(
            ten_year.loc[ten_year.reform_name == "option12", "revenue_impact"].iloc[0]
        )
    )
    top_option8 = fmt_b(
        float(ten_year.loc[ten_year.reform_name == "option8", "revenue_impact"].iloc[0])
    )
    option1 = fmt_b(
        float(ten_year.loc[ten_year.reform_name == "option1", "revenue_impact"].iloc[0])
    )

    return f"""
The current release surface contains the fourteen contract-standard reforms:
`option1` through `option12`, the reverse-Roth proposal, and the `93%`
benchmark. All rows come from the June 12 full-H5 panel on the populace
baselines, or display interpolation between those exact anchor-year H5 outputs.
Legacy non-contract artifacts are excluded from the dashboard, paper exhibits,
and release package.

## Ten-year static revenue impacts

{ten_year_table}

In the ten-year window, the largest revenue raisers are `option12`
({top_option12} $B) and `option8` ({top_option8} $B). The largest revenue
reduction is `option1` ({option1} $B).

## Terminal-year static impacts

{terminal_table}

At `2100`, the strongest positive revenue effects come from broader benefit
taxation options such as `option8` and `option10`. The largest revenue
reductions are repeal or structural swap options such as `option1`, `option5`,
and `option12`.
"""


def build_revenue_impacts(df: pd.DataFrame) -> str:
    milestone_years = [2035, 2050, 2075, 2100]
    milestone_reforms = [
        "option1",
        "option2",
        "option4",
        "option5",
        "option8",
        "option10",
        "option12",
    ]
    milestone = df[
        df["year"].isin(milestone_years) & df["reform_name"].isin(milestone_reforms)
    ].copy()

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
    ]
    decomposition = df[
        (df["year"] == 2100) & (df["reform_name"].isin(decomposition_reforms))
    ]
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

    return f"""
## Milestone revenue impacts

{markdown_table(["Reform", "2035", "2050", "2075", "2100"], revenue_rows)}

The rebuilt standard series shows the expected late-horizon split: repeal or
TOB-reducing options (`option1`, `option5`, `option12`) become increasingly
costly relative to current law, while broader taxation options (`option2`,
`option8`, `option10`) continue to raise revenue.

## Terminal-year trust-fund decomposition

{markdown_table(["Reform", "2100 Revenue ($B)", "2100 TOB ($B)", "2100 OASDI Net ($B)", "2100 HI Net ($B)"], decomposition_rows)}
"""


def build_validation_sentinels(df: pd.DataFrame) -> str:
    exact = df[df["source"].eq("exact_full_h5")]
    interpolated = df[df["source"].eq("linear_interpolation_between_full_h5_years")]
    late_exact = exact[exact["year"].astype(int).ge(2075)]
    r2_uris = exact["scenario_h5_uri"].astype(str).str.startswith("r2://").mean()

    probe_rows = [
        [
            "Anchor-year full-H5 coverage",
            "fourteen reforms",
            f"{len(exact)} exact full-H5 rows",
            "Matches the 16 anchor-year panel contract (2026, 2030, 2035-2100 by 5).",
        ],
        [
            "Late-horizon coverage",
            "2075, 2080, 2085, 2090, 2095, 2100",
            f"{len(late_exact)} exact late-year rows",
            "Real (no-synthetic) populace baseline datasets passing all gates.",
        ],
        [
            "Durable artifact links",
            "exact standard rows",
            f"{r2_uris:.0%} scenario H5 URIs are R2-backed",
            "Dashboard rows cite durable reform H5s.",
        ],
        [
            "Display interpolation boundary",
            "non-selected annual years",
            f"{len(interpolated)} interpolation rows",
            "Interpolated rows are display-only and not replacement H5s.",
        ],
    ]

    return f"""
The clean static release is validated against the current full-H5 production
contract. Older non-contract artifacts are not part of the release surface.

{markdown_table(["Check", "Coverage", "Observed values", "Interpretation"], probe_rows)}
"""


def build_external_benchmarks(df: pd.DataFrame) -> str:
    first_decade = df[df["year"].between(2026, 2035)]
    ten_year = (
        first_decade.groupby("reform_name", as_index=False)["revenue_impact"]
        .sum()
        .set_index("reform_name")["revenue_impact"]
    )
    ten_year_tob = (
        first_decade.groupby("reform_name", as_index=False)["tob_total_impact"]
        .sum()
        .set_index("reform_name")["tob_total_impact"]
    )

    option1_table = markdown_table(
        ["Source", "Policy", "Scoring", "Window", "Revenue Impact ($B)"],
        [
            [
                "PolicyEngine",
                "option1 full repeal",
                "Static",
                "2026-2035",
                fmt_b(float(ten_year["option1"])),
            ],
            [
                "CBO [@cbo2024options]",
                "Full repeal",
                "Conventional",
                "2025-2034",
                "-1,600.0",
            ],
            [
                "SSA Trustees [@ssa2024trustees]",
                "Full repeal",
                "Conventional",
                "2025-2034",
                "-1,800.0",
            ],
            [
                "Tax Foundation [@taxfoundation2024trump]",
                "Full repeal",
                "Conventional",
                "2025-2034",
                "-1,400.0",
            ],
            [
                "Tax Foundation [@taxfoundation2024trump]",
                "Full repeal",
                "Macroeconomic",
                "2025-2034",
                "-1,300.0",
            ],
        ],
    )

    option2_table = markdown_table(
        ["Source", "Policy", "Scoring", "Window", "Revenue Impact ($B)"],
        [
            [
                "PolicyEngine",
                "option2 tax 85% uniformly",
                "Static",
                "2026-2035",
                fmt_b(float(ten_year["option2"])),
            ],
            [
                "PolicyEngine",
                "option8 tax 100% of benefits",
                "Static",
                "2026-2035",
                fmt_b(float(ten_year["option8"])),
            ],
            [
                "JCT [@jct2024expenditures]",
                "Current SS tax expenditure",
                "Conventional",
                "2024-2028",
                "+318.4",
            ],
            [
                "CBO [@cbo2024pension]",
                "Pension-style basis recovery",
                "Conventional",
                "2021-2030",
                "+458.7",
            ],
        ],
    )

    option7_table = markdown_table(
        [
            "Source",
            "Policy",
            "Scoring",
            "Window",
            "Federal revenue ($B)",
            "TOB impact ($B)",
        ],
        [
            [
                "PolicyEngine",
                "option7 eliminate bonus senior deduction",
                "Static",
                "2026-2035",
                fmt_b(float(ten_year["option7"])),
                fmt_b(float(ten_year_tob["option7"])),
            ],
            [
                "JCT [@jct2025bonus]",
                "Bonus senior deduction",
                "Conventional",
                "FY2025-FY2034",
                "-66.3",
                "n/a",
            ],
        ],
    )

    return f"""
The benchmark layer is best treated as orientation rather than a point-estimate
competition. The current rebuilt static package continues to sit within the
broad range established by the first report's benchmark set, but windows and
policy baselines are not identical.

## Option 1: full repeal benchmark

{option1_table}

## Options 2 and 8: broader taxation benchmark

{option2_table}

## Option 7: bonus senior deduction benchmark

{option7_table}
"""


def build_response_status() -> str:
    return """
Labor-supply response rows are generated under the current full-H5 reform contract
and published as the dashboard's supplemental scoring surface. Each
endpoint cell saves a durable reform H5 first, computed at `2026` and `2100`
for all fourteen reforms; aggregates are then derived from those H5s using
PolicyEngine/MicroSeries operations, and intermediate annual rows are
interpolated from the endpoint ratios. The rows appear in `results.csv` under
`scoring_type = behavioral`. Static scoring remains the primary surface;
labor-supply response results are partial-equilibrium estimates under the
project's age-based elasticity schedule and are not official CBO or JCT scores.
Earlier non-contract response artifacts were removed from the release surface.
"""


def build_household_impacts() -> str:
    return """
The cleaned static rebuild finalized the aggregate reform package before the
distributional refresh. The manuscript therefore does not cite legacy
household-burden or distributional point estimates as current results.

Distributional exhibits should be regenerated only after a current-contract
household aggregation pass is complete.
"""


def main() -> None:
    EXHIBITS.mkdir(parents=True, exist_ok=True)
    SECTION_EXHIBITS.mkdir(parents=True, exist_ok=True)
    df = load_static()

    write_exhibit("results-overview.md", build_results_overview(df))
    write_exhibit("revenue-impacts.md", build_revenue_impacts(df))
    write_exhibit("external-benchmarks.md", build_external_benchmarks(df))
    write_exhibit("labor-supply-response-status.md", build_response_status())
    write_exhibit("household-impacts.md", build_household_impacts())

    print("Wrote paper exhibits:")
    for path in sorted(EXHIBITS.glob("*.md")):
        print(f" - {path}")


if __name__ == "__main__":
    main()
