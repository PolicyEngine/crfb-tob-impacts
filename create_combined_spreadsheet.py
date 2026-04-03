"""
Create a combined spreadsheet with all reform data for both static and dynamic scoring.

Uses the same allocation logic as dataLoader.ts in the dashboard.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from src.trust_fund_allocation import split_revenue_impacts


REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "dashboard" / "public" / "data"
ECONOMIC_PROJECTIONS_PATH = DATA_DIR / "ssa_economic_projections.csv"
HI_TAXABLE_PAYROLL_PATH = DATA_DIR / "hi_taxable_payroll.csv"
STATIC_RESULTS_PATH = DATA_DIR / "all_static_results.csv"
DYNAMIC_RESULTS_PATH = DATA_DIR / "all_dynamic_results.csv"
OUTPUT_PATH = REPO_ROOT / "dashboard_data_combined.csv"
DEFAULT_ECONOMIC_ROW = {"taxable_payroll": 0.0, "hi_taxable_payroll": 0.0, "gdp": 0.0}


def load_economic_projections() -> dict[int, dict[str, float]]:
    econ = pd.read_csv(ECONOMIC_PROJECTIONS_PATH)
    hi_taxable_payroll = pd.read_csv(HI_TAXABLE_PAYROLL_PATH)
    econ = econ.merge(hi_taxable_payroll, on="year", how="left")
    return econ.set_index("year").to_dict(orient="index")


def load_results() -> pd.DataFrame:
    static_df = pd.read_csv(STATIC_RESULTS_PATH)
    dynamic_df = pd.read_csv(DYNAMIC_RESULTS_PATH)
    return pd.concat([static_df, dynamic_df], ignore_index=True)


def percentage(value: float, denominator: float) -> float:
    return (value / denominator * 100) if denominator > 0 else 0.0


def resolve_hi_taxable_payroll(econ_row: dict[str, float], taxable_payroll: float) -> float:
    hi_taxable_payroll = float(econ_row.get("hi_taxable_payroll", taxable_payroll))
    if pd.isna(hi_taxable_payroll) or hi_taxable_payroll <= 0:
        return taxable_payroll
    return hi_taxable_payroll


def build_combined_dataframe(
    combined: pd.DataFrame,
    economic_projections: dict[int, dict[str, float]],
) -> pd.DataFrame:
    rows = []

    for _, row in combined.iterrows():
        year = int(row["year"])
        revenue_impact, oasdi_impact, hi_impact = split_revenue_impacts(row)

        econ_row = economic_projections.get(year, DEFAULT_ECONOMIC_ROW)
        taxable_payroll = float(econ_row["taxable_payroll"])
        gdp = float(econ_row["gdp"])
        hi_taxable_payroll = resolve_hi_taxable_payroll(econ_row, taxable_payroll)

        rows.append(
            {
                "Reform": row["reform_name"],
                "Year": year,
                "Revenue impact (B)": round(revenue_impact, 2),
                "OASDI revenue impact (B)": round(oasdi_impact, 2),
                "HI revenue impact (B)": round(hi_impact, 2),
                "Type": row["scoring_type"],
                "OASDI taxable payroll (B)": round(taxable_payroll, 2),
                "HI taxable payroll (B)": round(hi_taxable_payroll, 2),
                "GDP (B)": round(gdp, 2),
                "% of OASDI taxable payroll": round(
                    percentage(revenue_impact, taxable_payroll), 4
                ),
                "% of GDP": round(percentage(revenue_impact, gdp), 4),
                "OASDI % of OASDI taxable payroll": round(
                    percentage(oasdi_impact, taxable_payroll), 4
                ),
                "HI % of HI taxable payroll": round(
                    percentage(hi_impact, hi_taxable_payroll), 4
                ),
                "OASDI % of GDP": round(percentage(oasdi_impact, gdp), 4),
                "HI % of GDP": round(percentage(hi_impact, gdp), 4),
            }
        )

    result_df = pd.DataFrame(rows)
    return result_df.sort_values(["Reform", "Type", "Year"])


def print_sample(result_df: pd.DataFrame, reform: str, scoring_type: str, year: int) -> None:
    sample = result_df[
        (result_df["Reform"] == reform)
        & (result_df["Type"] == scoring_type)
        & (result_df["Year"] == year)
    ]
    print(sample.to_string(index=False))


def print_summary(result_df: pd.DataFrame) -> None:
    print(f"Created {OUTPUT_PATH.name} with {len(result_df)} rows")
    print(f"\nColumns: {list(result_df.columns)}")
    print(f"\nReforms: {sorted(result_df['Reform'].unique())}")
    print(f"Types: {result_df['Type'].unique()}")
    print(f"Years: {result_df['Year'].min()} - {result_df['Year'].max()}")

    print("\n--- Sample: Option 3, Static, 2029 (shows baseline allocation) ---")
    print_sample(result_df, "option3", "static", 2029)

    print("\n--- Sample: Option 7, Static, 2026 (shows general revenue allocation) ---")
    print_sample(result_df, "option7", "static", 2026)


def main() -> None:
    economic_projections = load_economic_projections()
    combined = load_results()
    result_df = build_combined_dataframe(combined, economic_projections)
    result_df.to_csv(OUTPUT_PATH, index=False)
    print_summary(result_df)


if __name__ == "__main__":
    main()
