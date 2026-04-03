from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


KEY_COLUMNS = ["reform_name", "year"]
VALUE_COLUMNS = [
    "revenue_impact",
    "baseline_tob_oasdi",
    "baseline_tob_medicare_hi",
    "baseline_tob_total",
    "tob_oasdi_impact",
    "tob_medicare_hi_impact",
    "oasdi_net_impact",
    "hi_net_impact",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two result vintages for selected reforms and years."
    )
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--reforms",
        required=True,
        help="Comma-separated reform IDs to include.",
    )
    parser.add_argument(
        "--years",
        required=True,
        help="Comma-separated years to include.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional CSV path for the merged comparison output.",
    )
    return parser.parse_args()


def load_results(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [column for column in [*KEY_COLUMNS, *VALUE_COLUMNS] if column not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    return df[KEY_COLUMNS + VALUE_COLUMNS].copy()


def filter_results(
    df: pd.DataFrame,
    reforms: list[str],
    years: list[int],
) -> pd.DataFrame:
    filtered = df[df["reform_name"].isin(reforms) & df["year"].isin(years)].copy()
    return filtered.sort_values(KEY_COLUMNS).reset_index(drop=True)


def build_comparison(
    baseline_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
) -> pd.DataFrame:
    merged = baseline_df.merge(
        candidate_df,
        on=KEY_COLUMNS,
        suffixes=("_baseline", "_candidate"),
        validate="one_to_one",
    )

    for column in VALUE_COLUMNS:
        merged[f"{column}_delta"] = (
            merged[f"{column}_candidate"] - merged[f"{column}_baseline"]
        )

    ordered_columns = KEY_COLUMNS.copy()
    for column in VALUE_COLUMNS:
        ordered_columns.extend(
            [
                f"{column}_baseline",
                f"{column}_candidate",
                f"{column}_delta",
            ]
        )
    return merged[ordered_columns]


def print_summary(df: pd.DataFrame) -> None:
    summary_columns = [
        "reform_name",
        "year",
        "revenue_impact_delta",
        "baseline_tob_oasdi_delta",
        "baseline_tob_medicare_hi_delta",
        "tob_oasdi_impact_delta",
        "tob_medicare_hi_impact_delta",
    ]
    print(df[summary_columns].to_string(index=False))


def main() -> None:
    args = parse_args()
    reforms = [reform.strip() for reform in args.reforms.split(",")]
    years = [int(year.strip()) for year in args.years.split(",")]

    baseline_df = filter_results(load_results(args.baseline), reforms, years)
    candidate_df = filter_results(load_results(args.candidate), reforms, years)
    comparison = build_comparison(baseline_df, candidate_df)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        comparison.to_csv(args.output, index=False)
        print(f"Wrote {args.output}")

    print_summary(comparison)


if __name__ == "__main__":
    main()
