from __future__ import annotations

from pathlib import Path

import pandas as pd


REPO = Path("/Users/maxghenis/PolicyEngine/crfb-tob-impacts")
RESULTS = REPO / "results"
EXHIBITS = REPO / "paper" / "exhibits"
SECTION_EXHIBITS = REPO / "paper" / "sections" / "exhibits"
DYNAMIC = RESULTS / "all_dynamic_results_latesthf_2026_2100_standard_options.csv"
STATIC = RESULTS / "trustees_modal_2026_2100_all_reforms_small_deployed_latesthf_stitched_billions.csv"

FOCUS_REFORMS = [
    "option1",
    "option2",
    "option4",
    "option5",
    "option6",
    "option7",
    "option8",
    "option10",
    "option11",
    "option12",
]


def fmt_b(value: float) -> str:
    return f"{value:+,.1f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_exhibit(name: str, text: str) -> None:
    write(EXHIBITS / name, text)
    write(SECTION_EXHIBITS / name, text)


def load_dynamic() -> pd.DataFrame:
    return pd.read_csv(DYNAMIC).sort_values(["year", "reform_name"]).reset_index(drop=True)


def load_static() -> pd.DataFrame:
    df = pd.read_csv(STATIC)
    return df[df["reform_name"].isin({f"option{i}" for i in range(1, 13)})].sort_values(
        ["year", "reform_name"]
    )


def build_dynamic_results(dynamic_df: pd.DataFrame, static_df: pd.DataFrame) -> str:
    dynamic_10 = (
        dynamic_df[dynamic_df["year"].between(2026, 2035)]
        .groupby("reform_name", as_index=False)["revenue_impact"]
        .sum()
    )
    static_10 = (
        static_df[static_df["year"].between(2026, 2035)]
        .groupby("reform_name", as_index=False)["revenue_impact"]
        .sum()
        .rename(columns={"revenue_impact": "static_revenue_impact"})
    )
    ten_year = dynamic_10.merge(static_10, on="reform_name", how="left")
    ten_year["dynamic_minus_static"] = (
        ten_year["revenue_impact"] - ten_year["static_revenue_impact"]
    )
    ten_year = ten_year[ten_year["reform_name"].isin(FOCUS_REFORMS)]

    ten_year_rows = [
        [
            row.reform_name,
            fmt_b(row.revenue_impact),
            fmt_b(row.dynamic_minus_static),
        ]
        for row in ten_year.sort_values("revenue_impact").itertuples()
    ]

    terminal = dynamic_df[dynamic_df["year"] == 2100].merge(
        static_df[static_df["year"] == 2100][
            ["reform_name", "revenue_impact", "tob_total_impact"]
        ].rename(
            columns={
                "revenue_impact": "static_revenue_impact",
                "tob_total_impact": "static_tob_total_impact",
            }
        ),
        on="reform_name",
        how="left",
    )
    terminal["dynamic_minus_static"] = (
        terminal["revenue_impact"] - terminal["static_revenue_impact"]
    )
    terminal = terminal[terminal["reform_name"].isin(FOCUS_REFORMS)]

    terminal_rows = [
        [
            row.reform_name,
            fmt_b(row.revenue_impact),
            fmt_b(row.tob_total_impact),
            fmt_b(row.dynamic_minus_static),
        ]
        for row in terminal.sort_values("revenue_impact").itertuples()
    ]

    option7_active = dynamic_df[
        (dynamic_df["reform_name"] == "option7") & (dynamic_df["revenue_impact"].abs() > 1e-9)
    ][["year", "revenue_impact"]]
    option7_rows = [
        [str(int(row.year)), fmt_b(float(row.revenue_impact))]
        for row in option7_active.itertuples()
    ]

    ten_year_table = markdown_table(
        ["Reform", "Dynamic 2026-2035 ($B)", "Dynamic minus static ($B)"],
        ten_year_rows,
    )
    terminal_table = markdown_table(
        ["Reform", "Dynamic 2100 ($B)", "Dynamic 2100 TOB ($B)", "Dynamic minus static ($B)"],
        terminal_rows,
    )
    option7_table = markdown_table(["Year", "Dynamic revenue impact ($B)"], option7_rows)

    return f"""
## Dynamic standard-panel summary

The conventional dynamic release now covers the standard reforms `option1`
through `option12` on the same Trustees baseline lineage as the cleaned static
series. The main behavioral difference is the age-based labor-supply response
layer, not a different baseline family. The balanced-fix special cases
`option13` and `option14_stacked` are intentionally omitted from the public
dynamic release because they would require a separate iterative post-response
solve rather than the shipped standard dynamic pipeline.

### Ten-year dynamic revenue effects

{ten_year_table}

In the first decade, dynamic scoring still leaves `option12`, `option6`, and
`option8` as the largest revenue raisers, while `option1` remains the largest
revenue loss. Relative to static, the biggest first-decade dynamic shifts are a
smaller gain for `option12` and `option6`, and a less negative result for
`option1`.

### Terminal-year dynamic effects

{terminal_table}

By `2100`, the dynamic series amplifies the same broad ranking as the static
series: `option8`, `option10`, and `option9` remain the largest revenue
raisers, while `option1`, `option5`, `option6`, and `option12` are much more
negative than in the static run. `option11` remains distinct from `option2`
early in the horizon and then converges toward it late.

### Dynamic `option7`

{option7_table}

The old late-horizon `option7` anomaly does not return under the cleaned
dynamic contract. The option is positive only in `2026-2028` and exactly zero
after that.
"""


def main() -> int:
    dynamic_df = load_dynamic()
    static_df = load_static()
    write_exhibit("dynamic-results.md", build_dynamic_results(dynamic_df, static_df))
    print(f"Wrote {EXHIBITS / 'dynamic-results.md'}")
    print(f"Wrote {SECTION_EXHIBITS / 'dynamic-results.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
