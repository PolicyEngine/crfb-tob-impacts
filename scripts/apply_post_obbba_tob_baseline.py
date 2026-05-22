# ruff: noqa: E402

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tob_baseline import (
    GENERATED_BASELINE_PATH,
    HI_METHOD_MATCH_OASDI_PCT_CHANGE,
    HI_METHODS,
    build_tob_baseline,
    validate_generated_baseline,
    write_tob_baseline,
    write_tob_baseline_manifest,
)

BASELINE_PATH = GENERATED_BASELINE_PATH
BASELINE_COLUMNS = [
    "baseline_tob_oasdi",
    "baseline_tob_medicare_hi",
    "baseline_tob_total",
]
TARGET_COLUMNS = [
    "target_tob_oasdi",
    "target_tob_medicare_hi",
    "target_tob_total",
]
SAMPLE_YEAR = 2026
SPECIAL_START_YEAR = 2035
CURRENT_LAW_TOB_REFORMS = {f"option{i}" for i in range(1, 14)}
EMPLOYER_SWAP_REFORMS = {"option5", "option6", "option12"}
RESULT_PATHS = [
    REPO_ROOT / "results" / "all_static_results_full_h5_selected_panel_display_20260522.csv",
    REPO_ROOT / "results" / "results_full_h5_selected_panel_display_20260522.csv",
    REPO_ROOT / "dashboard" / "public" / "data" / "results.csv",
    REPO_ROOT / "results.csv",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and apply a post-OBBBA TOB baseline to result CSVs."
    )
    parser.add_argument(
        "--hi-method",
        choices=sorted(HI_METHODS),
        default=HI_METHOD_MATCH_OASDI_PCT_CHANGE,
        help="How to bridge the annual HI path while the public CMS post-OBBBA series is unresolved.",
    )
    return parser.parse_args()


def load_baseline() -> pd.DataFrame:
    baseline = pd.read_csv(BASELINE_PATH)
    baseline = baseline.rename(
        columns={
            "tob_oasdi_billions": "target_tob_oasdi",
            "tob_hi_billions": "target_tob_medicare_hi",
            "tob_total_billions": "target_tob_total",
        }
    )
    return baseline[["year", *TARGET_COLUMNS]]


def current_law_tob_mask(df: pd.DataFrame) -> pd.Series:
    reform = df["reform_name"].astype(str)
    year = df["year"].astype(int)
    return reform.isin(CURRENT_LAW_TOB_REFORMS) | (
        reform.eq("option14_stacked") & year.lt(SPECIAL_START_YEAR)
    )


def generate_baseline(hi_method: str) -> None:
    baseline = build_tob_baseline(hi_method)
    validate_generated_baseline(baseline)
    write_tob_baseline(baseline, BASELINE_PATH)
    manifest = write_tob_baseline_manifest(BASELINE_PATH)

    sample = baseline.loc[baseline["year"] == SAMPLE_YEAR].iloc[0]
    print(
        f"Generated {BASELINE_PATH.relative_to(REPO_ROOT)} "
        f"using HI method '{hi_method}': "
        f"{SAMPLE_YEAR} OASDI={sample['tob_oasdi_billions']:.4f} "
        f"HI={sample['tob_hi_billions']:.4f} "
        f"Total={sample['tob_total_billions']:.4f}"
    )
    print(
        "Manifest "
        f"{BASELINE_PATH.with_suffix('.manifest.json').relative_to(REPO_ROOT)} "
        f"sha256={manifest['baseline_sha256']}"
    )


def apply_override(result_path: Path, baseline: pd.DataFrame) -> None:
    df = pd.read_csv(result_path)
    merged = df.merge(
        baseline,
        on="year",
        how="left",
        suffixes=("", "_override"),
        validate="many_to_one",
    )

    missing_years = sorted(merged.loc[merged["target_tob_oasdi"].isna(), "year"].unique())
    if missing_years:
        raise ValueError(f"{result_path} is missing baseline rows for years: {missing_years}")

    mask = current_law_tob_mask(merged)
    calibrated = merged.copy()
    baseline_delta_total = pd.Series(0.0, index=calibrated.index)
    reform_delta_total = pd.Series(0.0, index=calibrated.index)

    fund_specs = [
        (
            "baseline_tob_oasdi",
            "reform_tob_oasdi",
            "tob_oasdi_impact",
            "target_tob_oasdi",
            "oasdi_loss",
        ),
        (
            "baseline_tob_medicare_hi",
            "reform_tob_medicare_hi",
            "tob_medicare_hi_impact",
            "target_tob_medicare_hi",
            "hi_loss",
        ),
    ]

    for baseline_col, reform_col, impact_col, target_col, loss_col in fund_specs:
        old_baseline = calibrated.loc[mask, baseline_col].astype(float)
        if old_baseline.le(0).any():
            bad = calibrated.loc[
                mask & calibrated[baseline_col].le(0),
                ["reform_name", "year", baseline_col],
            ]
            raise ValueError(
                f"Cannot apply post-OBBBA TOB baseline to {result_path} "
                "with non-positive baseline rows:\n"
                + bad.to_string(index=False)
            )

        target = calibrated.loc[mask, target_col].astype(float)
        factor = target / old_baseline
        old_reform = calibrated.loc[mask, reform_col].astype(float)
        new_reform = old_reform * factor

        baseline_delta_total.loc[mask] += target - old_baseline
        reform_delta_total.loc[mask] += new_reform - old_reform

        calibrated.loc[mask, baseline_col] = target
        calibrated.loc[mask, reform_col] = new_reform
        calibrated.loc[mask, impact_col] = new_reform - target
        if loss_col in calibrated.columns:
            calibrated.loc[mask, loss_col] = calibrated.loc[mask, loss_col].astype(
                float
            ) * factor

    calibrated.loc[mask, "baseline_tob_total"] = (
        calibrated.loc[mask, "baseline_tob_oasdi"]
        + calibrated.loc[mask, "baseline_tob_medicare_hi"]
    )
    calibrated.loc[mask, "reform_tob_total"] = (
        calibrated.loc[mask, "reform_tob_oasdi"]
        + calibrated.loc[mask, "reform_tob_medicare_hi"]
    )
    calibrated.loc[mask, "tob_total_impact"] = (
        calibrated.loc[mask, "reform_tob_total"]
        - calibrated.loc[mask, "baseline_tob_total"]
    )

    calibrated.loc[mask, "baseline_revenue"] = (
        calibrated.loc[mask, "baseline_revenue"].astype(float)
        + baseline_delta_total.loc[mask]
    )
    calibrated.loc[mask, "reform_revenue"] = (
        calibrated.loc[mask, "reform_revenue"].astype(float)
        + reform_delta_total.loc[mask]
    )
    calibrated.loc[mask, "revenue_impact"] = (
        calibrated.loc[mask, "reform_revenue"]
        - calibrated.loc[mask, "baseline_revenue"]
    )

    reform = calibrated["reform_name"].astype(str)
    swap_mask = mask & (
        reform.isin(EMPLOYER_SWAP_REFORMS)
        | (reform.eq("option14_stacked") & calibrated["year"].astype(int).lt(SPECIAL_START_YEAR))
    )
    calibrated.loc[swap_mask, "oasdi_net_impact"] = (
        calibrated.loc[swap_mask, "oasdi_gain"].astype(float)
        - calibrated.loc[swap_mask, "oasdi_loss"].astype(float)
    )
    calibrated.loc[swap_mask, "hi_net_impact"] = (
        calibrated.loc[swap_mask, "hi_gain"].astype(float)
        - calibrated.loc[swap_mask, "hi_loss"].astype(float)
    )

    direct_tob_mask = mask & ~swap_mask & ~reform.eq("option13")
    calibrated.loc[direct_tob_mask, "oasdi_net_impact"] = calibrated.loc[
        direct_tob_mask, "tob_oasdi_impact"
    ]
    calibrated.loc[direct_tob_mask, "hi_net_impact"] = calibrated.loc[
        direct_tob_mask, "tob_medicare_hi_impact"
    ]

    calibrated = calibrated.drop(columns=TARGET_COLUMNS)

    calibrated.to_csv(result_path, index=False, float_format="%.10f")

    sample = calibrated.loc[calibrated["year"] == SAMPLE_YEAR, BASELINE_COLUMNS].iloc[0]
    print(
        f"{result_path.relative_to(REPO_ROOT)}: "
        f"{SAMPLE_YEAR} OASDI={sample['baseline_tob_oasdi']:.4f} "
        f"HI={sample['baseline_tob_medicare_hi']:.4f} "
        f"Total={sample['baseline_tob_total']:.4f}"
    )


def regenerate_dashboard_results() -> None:
    subprocess.run(
        [sys.executable, "scripts/publish_dashboard_results.py"],
        cwd=REPO_ROOT,
        check=True,
    )


def main() -> None:
    args = parse_args()
    generate_baseline(args.hi_method)
    baseline = load_baseline()
    for result_path in RESULT_PATHS:
        if result_path.exists():
            apply_override(result_path, baseline)
    regenerate_dashboard_results()


if __name__ == "__main__":
    main()
