from __future__ import annotations

from pathlib import Path

import pandas as pd


REPO = Path("/Users/maxghenis/PolicyEngine/crfb-tob-impacts")
RESULTS = REPO / "results"
EXHIBITS = REPO / "paper" / "exhibits"
SECTION_EXHIBITS = REPO / "paper" / "sections" / "exhibits"
CONVENTIONAL_SOURCE = RESULTS / "all_dynamic_results_latesthf_2026_2100_standard_options.csv"
STATIC = RESULTS / "all_static_results_latesthf_2026_2100_14options.csv"

FOCUS_REFORMS = [
    "option1",
    "option2",
    "option4",
    "option5",
    "option6",
    "option7",
    "option8",
    "option9",
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


def load_conventional() -> pd.DataFrame:
    return pd.read_csv(CONVENTIONAL_SOURCE).sort_values(["year", "reform_name"]).reset_index(drop=True)


def load_static() -> pd.DataFrame:
    df = pd.read_csv(STATIC)
    return df[df["reform_name"].isin({f"option{i}" for i in range(1, 13)})].sort_values(
        ["year", "reform_name"]
    )


def validate_baseline_alignment(conventional_df: pd.DataFrame, static_df: pd.DataFrame) -> None:
    baseline_cols = [
        "baseline_revenue",
        "baseline_tob_medicare_hi",
        "baseline_tob_oasdi",
        "baseline_tob_total",
    ]
    merged = conventional_df[["reform_name", "year", *baseline_cols]].merge(
        static_df[["reform_name", "year", *baseline_cols]],
        on=["reform_name", "year"],
        suffixes=("_conventional", "_static"),
        how="inner",
    )
    if len(merged) != len(conventional_df):
        raise ValueError("Static reference does not cover all conventional rows.")

    mismatches: list[str] = []
    for column in baseline_cols:
        diff = (merged[f"{column}_conventional"] - merged[f"{column}_static"]).abs()
        max_diff = float(diff.max())
        if max_diff > 1e-6:
            row = merged.loc[diff.idxmax()]
            mismatches.append(
                f"{column} max diff {max_diff:.6g} at "
                f"{row['reform_name']} {int(row['year'])}"
            )

    if mismatches:
        raise ValueError(
            "Conventional baseline does not match the static reference; refusing "
            "to generate citable conventional exhibits. "
            + "; ".join(mismatches)
        )


def build_conventional_results(conventional_df: pd.DataFrame, static_df: pd.DataFrame) -> str:
    conventional_10 = (
        conventional_df[conventional_df["year"].between(2026, 2035)]
        .groupby("reform_name", as_index=False)["revenue_impact"]
        .sum()
    )
    static_10 = (
        static_df[static_df["year"].between(2026, 2035)]
        .groupby("reform_name", as_index=False)["revenue_impact"]
        .sum()
        .rename(columns={"revenue_impact": "static_revenue_impact"})
    )
    ten_year = conventional_10.merge(static_10, on="reform_name", how="left")
    ten_year["conventional_minus_static"] = (
        ten_year["revenue_impact"] - ten_year["static_revenue_impact"]
    )
    ten_year = ten_year[ten_year["reform_name"].isin(FOCUS_REFORMS)]

    ten_year_rows = [
        [
            row.reform_name,
            fmt_b(row.revenue_impact),
            fmt_b(row.conventional_minus_static),
        ]
        for row in ten_year.sort_values("revenue_impact").itertuples()
    ]

    terminal = conventional_df[conventional_df["year"] == 2100].merge(
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
    terminal["conventional_minus_static"] = (
        terminal["revenue_impact"] - terminal["static_revenue_impact"]
    )
    terminal = terminal[terminal["reform_name"].isin(FOCUS_REFORMS)]

    terminal_rows = [
        [
            row.reform_name,
            fmt_b(row.revenue_impact),
            fmt_b(row.tob_total_impact),
            fmt_b(row.conventional_minus_static),
        ]
        for row in terminal.sort_values("revenue_impact").itertuples()
    ]

    option7_active = conventional_df[
        (conventional_df["reform_name"] == "option7")
        & (conventional_df["revenue_impact"].abs() > 1e-9)
    ][["year", "revenue_impact"]]
    option7_rows = [
        [str(int(row.year)), fmt_b(float(row.revenue_impact))]
        for row in option7_active.itertuples()
    ]

    ten_year_table = markdown_table(
        ["Reform", "Conventional 2026-2035 ($B)", "Conventional minus static ($B)"],
        ten_year_rows,
    )
    terminal_table = markdown_table(
        [
            "Reform",
            "Conventional 2100 ($B)",
            "Conventional 2100 TOB ($B)",
            "Conventional minus static ($B)",
        ],
        terminal_rows,
    )
    option7_table = markdown_table(["Year", "Conventional revenue impact ($B)"], option7_rows)

    return f"""
## Conventional standard-panel summary

The conventional release now covers the standard reforms `option1`
through `option12` on the same Trustees baseline lineage as the cleaned static
series. The main behavioral difference is the age-based labor-supply response
layer, not a different baseline family. The balanced-fix special cases
`option13` and `option14_stacked` are intentionally omitted from the public
conventional release because they would require a separate iterative
post-response solve rather than the shipped standard conventional pipeline.

### Ten-year conventional revenue effects

{ten_year_table}

In the first decade, conventional scoring still leaves `option12`, `option6`,
and `option8` as the largest revenue raisers, while `option1` remains the
largest revenue loss. Relative to static, the biggest first-decade conventional
shifts are a smaller gain for `option12` and `option6`, and a less negative
result for `option1`.

### Terminal-year conventional effects

{terminal_table}

By `2100`, the conventional series amplifies the same broad ranking as the static
series: `option8`, `option10`, and `option9` remain the largest revenue
raisers, while `option1`, `option5`, `option6`, and `option12` are much more
negative than in the static run. `option11` remains distinct from `option2`
early in the horizon and then converges toward it late.

### Conventional `option7`

{option7_table}

The old late-horizon `option7` anomaly does not return under the cleaned
conventional contract. The option is positive only in `2026-2028` and exactly
zero after that.
"""


def main() -> int:
    conventional_df = load_conventional()
    static_df = load_static()
    validate_baseline_alignment(conventional_df, static_df)
    write_exhibit(
        "conventional-results.md",
        build_conventional_results(conventional_df, static_df),
    )
    print(f"Wrote {EXHIBITS / 'conventional-results.md'}")
    print(f"Wrote {SECTION_EXHIBITS / 'conventional-results.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
