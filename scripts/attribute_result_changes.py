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
        description=(
            "Decompose result changes into refresh-only, OACT-only, and total deltas."
        )
    )
    parser.add_argument("--published", required=True, type=Path)
    parser.add_argument("--refresh-only", required=True, type=Path)
    parser.add_argument("--refresh-oact", required=True, type=Path)
    parser.add_argument("--reforms", required=True)
    parser.add_argument("--years", required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_results(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [column for column in [*KEY_COLUMNS, *VALUE_COLUMNS] if column not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    return df[KEY_COLUMNS + VALUE_COLUMNS].copy()


def filter_results(df: pd.DataFrame, reforms: list[str], years: list[int]) -> pd.DataFrame:
    filtered = df[df["reform_name"].isin(reforms) & df["year"].isin(years)].copy()
    return filtered.sort_values(KEY_COLUMNS).reset_index(drop=True)


def build_attribution(
    published_df: pd.DataFrame,
    refresh_only_df: pd.DataFrame,
    refresh_oact_df: pd.DataFrame,
) -> pd.DataFrame:
    merged = published_df.merge(
        refresh_only_df,
        on=KEY_COLUMNS,
        suffixes=("_published", "_refresh_only"),
        validate="one_to_one",
    ).merge(
        refresh_oact_df,
        on=KEY_COLUMNS,
        validate="one_to_one",
    )

    renamed = {
        column: f"{column}_refresh_oact"
        for column in VALUE_COLUMNS
    }
    merged = merged.rename(columns=renamed)

    ordered_columns = KEY_COLUMNS.copy()
    for column in VALUE_COLUMNS:
        merged[f"{column}_refresh_delta"] = (
            merged[f"{column}_refresh_only"] - merged[f"{column}_published"]
        )
        merged[f"{column}_oact_delta"] = (
            merged[f"{column}_refresh_oact"] - merged[f"{column}_refresh_only"]
        )
        merged[f"{column}_total_delta"] = (
            merged[f"{column}_refresh_oact"] - merged[f"{column}_published"]
        )
        ordered_columns.extend(
            [
                f"{column}_published",
                f"{column}_refresh_only",
                f"{column}_refresh_oact",
                f"{column}_refresh_delta",
                f"{column}_oact_delta",
                f"{column}_total_delta",
            ]
        )

    return merged[ordered_columns]


def print_summary(df: pd.DataFrame) -> None:
    columns = [
        "reform_name",
        "year",
        "revenue_impact_refresh_delta",
        "revenue_impact_oact_delta",
        "revenue_impact_total_delta",
        "tob_oasdi_impact_refresh_delta",
        "tob_oasdi_impact_oact_delta",
        "tob_medicare_hi_impact_refresh_delta",
        "tob_medicare_hi_impact_oact_delta",
    ]
    print(df[columns].to_string(index=False))


def main() -> None:
    args = parse_args()
    reforms = [reform.strip() for reform in args.reforms.split(",") if reform.strip()]
    years = [int(year.strip()) for year in args.years.split(",") if year.strip()]

    published_df = filter_results(load_results(args.published), reforms, years)
    refresh_only_df = filter_results(load_results(args.refresh_only), reforms, years)
    refresh_oact_df = filter_results(load_results(args.refresh_oact), reforms, years)

    attribution = build_attribution(published_df, refresh_only_df, refresh_oact_df)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        attribution.to_csv(args.output, index=False)
        print(f"Wrote {args.output}")

    print_summary(attribution)


if __name__ == "__main__":
    main()
