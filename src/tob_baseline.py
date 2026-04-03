from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_LAW_PATH = REPO_ROOT / "data" / "tob_current_law_tr2025.csv"
OACT_OASDI_DELTA_PATH = REPO_ROOT / "data" / "oasdi_oact_20250805_nominal_delta.csv"
SSA_ECONOMIC_PROJECTIONS_PATH = REPO_ROOT / "data" / "ssa_economic_projections.csv"
GENERATED_BASELINE_PATH = REPO_ROOT / "data" / "ssa_tob_baseline_75year.csv"

REQUIRED_CURRENT_LAW_COLUMNS = {
    "year",
    "tob_oasdi_billions",
    "tob_hi_billions",
    "tob_total_billions",
}

HI_METHOD_CURRENT_LAW = "current_law"
HI_METHOD_MATCH_OASDI_PCT_CHANGE = "match_oasdi_pct_change"
HI_METHODS = {
    HI_METHOD_CURRENT_LAW,
    HI_METHOD_MATCH_OASDI_PCT_CHANGE,
}

SOURCE_OASDI = (
    "SSA OACT Aug. 5, 2025 letter Table 1b.n nominal OASDI cash flow change"
)
SOURCE_CURRENT_LAW = "2025 Trustees current-law TOB baseline"
SOURCE_HI_CMS_DIRECTION = (
    "CMS FY2025 Financial Report direction only; annual HI path bridged in code"
)


def load_current_law_series() -> pd.DataFrame:
    current_law = pd.read_csv(CURRENT_LAW_PATH)
    missing_columns = REQUIRED_CURRENT_LAW_COLUMNS - set(current_law.columns)
    if missing_columns:
        raise ValueError(
            f"Missing current-law TOB columns in {CURRENT_LAW_PATH.name}: {sorted(missing_columns)}"
        )

    payroll = pd.read_csv(SSA_ECONOMIC_PROJECTIONS_PATH, usecols=["year", "taxable_payroll"])
    payroll_2025 = pd.DataFrame([{"year": 2025, "taxable_payroll": 10621.0}])
    payroll = pd.concat([payroll_2025, payroll], ignore_index=True)

    merged = current_law.merge(payroll, on="year", how="left", validate="one_to_one")
    missing_payroll_years = merged.loc[merged["taxable_payroll"].isna(), "year"].tolist()
    if missing_payroll_years:
        raise ValueError(f"Missing taxable payroll values for years: {missing_payroll_years}")

    merged = merged.rename(
        columns={
            "tob_oasdi_billions": "current_law_oasdi_billions",
            "tob_hi_billions": "current_law_hi_billions",
            "tob_total_billions": "current_law_total_billions",
        }
    )
    return merged.sort_values("year").reset_index(drop=True)


def load_oact_oasdi_deltas() -> pd.DataFrame:
    deltas = pd.read_csv(OACT_OASDI_DELTA_PATH)
    required_columns = {"year", "oasdi_nominal_delta_billions"}
    missing_columns = required_columns - set(deltas.columns)
    if missing_columns:
        raise ValueError(
            f"Missing OACT delta columns in {OACT_OASDI_DELTA_PATH.name}: {sorted(missing_columns)}"
        )

    deltas = deltas.sort_values("year").reset_index(drop=True)
    last_delta = float(deltas.iloc[-1]["oasdi_nominal_delta_billions"])
    deltas = pd.concat(
        [
            deltas,
            pd.DataFrame(
                [
                    {
                        "year": 2100,
                        "oasdi_nominal_delta_billions": last_delta,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    deltas["oasdi_delta_method"] = "oact_table_1b_nominal"
    deltas.loc[
        deltas["year"] == 2100,
        "oasdi_delta_method",
    ] = "carry_forward_2099_nominal_delta"
    return deltas


def _apply_hi_method(df: pd.DataFrame, hi_method: str) -> tuple[pd.Series, str]:
    if hi_method == HI_METHOD_CURRENT_LAW:
        return (
            df["current_law_hi_billions"],
            "Use the 2025 Trustees/CMS HI current-law series unchanged.",
        )

    if hi_method == HI_METHOD_MATCH_OASDI_PCT_CHANGE:
        oasdi_factor = df["tob_oasdi_billions"] / df["current_law_oasdi_billions"]
        return (
            df["current_law_hi_billions"] * oasdi_factor,
            "Scale HI by the same percentage change as OASDI until a public CMS annual HI post-OBBBA series is identified.",
        )

    raise ValueError(f"Unsupported HI method: {hi_method}")


def build_tob_baseline(hi_method: str) -> pd.DataFrame:
    if hi_method not in HI_METHODS:
        raise ValueError(f"HI method must be one of {sorted(HI_METHODS)}")

    current_law = load_current_law_series()
    oact_deltas = load_oact_oasdi_deltas()

    df = current_law.merge(oact_deltas, on="year", how="left", validate="one_to_one")
    missing_delta_years = df.loc[df["oasdi_nominal_delta_billions"].isna(), "year"].tolist()
    if missing_delta_years:
        raise ValueError(f"Missing OACT OASDI deltas for years: {missing_delta_years}")

    df["tob_oasdi_billions"] = (
        df["current_law_oasdi_billions"] + df["oasdi_nominal_delta_billions"]
    )
    df["tob_hi_billions"], hi_method_note = _apply_hi_method(df, hi_method)
    df["tob_total_billions"] = df["tob_oasdi_billions"] + df["tob_hi_billions"]
    df["oasdi_share"] = df["tob_oasdi_billions"] / df["tob_total_billions"]
    df["hi_share"] = df["tob_hi_billions"] / df["tob_total_billions"]
    df["hi_method"] = hi_method
    df["oasdi_source"] = SOURCE_OASDI
    df["hi_source"] = SOURCE_HI_CMS_DIRECTION
    df["current_law_source"] = SOURCE_CURRENT_LAW
    df["notes"] = hi_method_note

    return df[
        [
            "year",
            "tob_oasdi_billions",
            "tob_hi_billions",
            "tob_total_billions",
            "oasdi_share",
            "hi_share",
            "current_law_oasdi_billions",
            "current_law_hi_billions",
            "current_law_total_billions",
            "taxable_payroll",
            "oasdi_nominal_delta_billions",
            "oasdi_delta_method",
            "hi_method",
            "oasdi_source",
            "hi_source",
            "current_law_source",
            "notes",
        ]
    ].sort_values("year").reset_index(drop=True)


def validate_generated_baseline(df: pd.DataFrame) -> None:
    expected_years = list(range(2025, 2101))
    years = df["year"].tolist()
    if years != expected_years:
        raise ValueError("Generated baseline must contain one row for each year 2025-2100.")

    totals = df["tob_total_billions"]
    if (totals <= 0).any():
        bad_years = df.loc[totals <= 0, "year"].tolist()
        raise ValueError(f"Generated baseline has non-positive totals for years: {bad_years}")

    if not np.allclose(
        df["tob_oasdi_billions"] + df["tob_hi_billions"],
        df["tob_total_billions"],
        atol=1e-9,
    ):
        raise ValueError("OASDI + HI must equal total TOB revenue in every year.")

    if not np.allclose(df["oasdi_share"] + df["hi_share"], 1.0, atol=1e-9):
        raise ValueError("OASDI share + HI share must equal 1 in every year.")

    expected_oasdi = {
        2025: 57.0397,
        2026: 60.5901,
        2029: 80.9200,
        2099: 2010.4384,
        2100: 2089.4768,
    }
    for year, expected_value in expected_oasdi.items():
        actual_value = float(df.loc[df["year"] == year, "tob_oasdi_billions"].iloc[0])
        if not np.isclose(actual_value, expected_value, atol=1e-4):
            raise ValueError(
                f"Unexpected OASDI value for {year}: got {actual_value:.4f}, expected {expected_value:.4f}"
            )


def write_tob_baseline(df: pd.DataFrame, output_path: Path = GENERATED_BASELINE_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.10f")
