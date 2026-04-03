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
)

BASELINE_PATH = GENERATED_BASELINE_PATH
BASELINE_COLUMNS = [
    "baseline_tob_oasdi",
    "baseline_tob_medicare_hi",
    "baseline_tob_total",
]
SAMPLE_YEAR = 2026
RESULT_PATHS = [
    REPO_ROOT / "all_static_results.csv",
    REPO_ROOT / "all_dynamic_results.csv",
    REPO_ROOT / "dashboard" / "public" / "data" / "all_static_results.csv",
    REPO_ROOT / "dashboard" / "public" / "data" / "all_dynamic_results.csv",
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
            "tob_oasdi_billions": "baseline_tob_oasdi",
            "tob_hi_billions": "baseline_tob_medicare_hi",
            "tob_total_billions": "baseline_tob_total",
        }
    )
    return baseline[["year", *BASELINE_COLUMNS]]


def generate_baseline(hi_method: str) -> None:
    baseline = build_tob_baseline(hi_method)
    validate_generated_baseline(baseline)
    write_tob_baseline(baseline, BASELINE_PATH)

    sample = baseline.loc[baseline["year"] == SAMPLE_YEAR].iloc[0]
    print(
        f"Generated {BASELINE_PATH.relative_to(REPO_ROOT)} "
        f"using HI method '{hi_method}': "
        f"{SAMPLE_YEAR} OASDI={sample['tob_oasdi_billions']:.4f} "
        f"HI={sample['tob_hi_billions']:.4f} "
        f"Total={sample['tob_total_billions']:.4f}"
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

    missing_years = sorted(
        merged.loc[merged["baseline_tob_oasdi_override"].isna(), "year"].unique()
    )
    if missing_years:
        raise ValueError(f"{result_path} is missing baseline rows for years: {missing_years}")

    for column in BASELINE_COLUMNS:
        merged[column] = merged[f"{column}_override"]
        merged = merged.drop(columns=[f"{column}_override"])

    merged.to_csv(result_path, index=False, float_format="%.10f")

    sample = merged.loc[merged["year"] == SAMPLE_YEAR, BASELINE_COLUMNS].iloc[0]
    print(
        f"{result_path.relative_to(REPO_ROOT)}: "
        f"{SAMPLE_YEAR} OASDI={sample['baseline_tob_oasdi']:.4f} "
        f"HI={sample['baseline_tob_medicare_hi']:.4f} "
        f"Total={sample['baseline_tob_total']:.4f}"
    )


def regenerate_combined_csv() -> None:
    subprocess.run(
        [sys.executable, "create_combined_spreadsheet.py"],
        cwd=REPO_ROOT,
        check=True,
    )


def main() -> None:
    args = parse_args()
    generate_baseline(args.hi_method)
    baseline = load_baseline()
    for result_path in RESULT_PATHS:
        apply_override(result_path, baseline)
    regenerate_combined_csv()


if __name__ == "__main__":
    main()
