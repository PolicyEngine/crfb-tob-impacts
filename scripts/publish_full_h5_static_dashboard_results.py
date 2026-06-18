from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DEFAULT_FULL_H5_AGGREGATE = (
    REPO / "results" / "modal_runs_production" / "static_cells.csv"
)
DEFAULT_REFERENCE_STATIC = REPO / "results.csv"
EXACT_BASELINE_SOURCE = "v2pop_tr2026_baseline_h5"
DEFAULT_TOB_BASELINE = REPO / "data" / "ssa_tob_baseline_75year.csv"
DEFAULT_EXACT_OUTPUT = REPO / "tmp" / "static_exact_preview.csv"
DEFAULT_DISPLAY_OUTPUT = REPO / "tmp" / "static_display_preview.csv"
DEFAULT_METADATA_OUTPUT = REPO / "tmp" / "static_display_preview.metadata.json"

STANDARD_REFORMS = tuple(f"option{i}" for i in range(1, 13)) + (
    "reverse_roth",
    "tax93",
)
ANNUAL_YEARS = tuple(range(2026, 2101))
REQUIRED_EXACT_YEARS = (2026, 2030) + tuple(range(2035, 2101, 5))
EXPECTED_EXACT_CELL_COUNT = len(STANDARD_REFORMS) * len(REQUIRED_EXACT_YEARS)

DOLLAR_COLUMNS = (
    "baseline_revenue",
    "reform_revenue",
    "revenue_impact",
    "baseline_tob_medicare_hi",
    "reform_tob_medicare_hi",
    "tob_medicare_hi_impact",
    "baseline_tob_oasdi",
    "reform_tob_oasdi",
    "tob_oasdi_impact",
    "baseline_tob_total",
    "reform_tob_total",
    "tob_total_impact",
    "employer_ss_tax_revenue",
    "employer_medicare_tax_revenue",
    "oasdi_gain",
    "hi_gain",
    "oasdi_loss",
    "hi_loss",
    "oasdi_net_impact",
    "hi_net_impact",
)

DASHBOARD_COLUMNS = (
    "reform_name",
    "year",
    "baseline_revenue",
    "reform_revenue",
    "revenue_impact",
    "baseline_tob_medicare_hi",
    "reform_tob_medicare_hi",
    "tob_medicare_hi_impact",
    "baseline_tob_oasdi",
    "reform_tob_oasdi",
    "tob_oasdi_impact",
    "baseline_tob_total",
    "reform_tob_total",
    "tob_total_impact",
    "scoring_type",
    "employer_ss_tax_revenue",
    "employer_medicare_tax_revenue",
    "oasdi_gain",
    "hi_gain",
    "oasdi_loss",
    "hi_loss",
    "oasdi_net_impact",
    "hi_net_impact",
)


def _scale_dollars_to_billions(frame: pd.DataFrame) -> pd.DataFrame:
    scaled = frame.copy()
    for column in DOLLAR_COLUMNS:
        if column in scaled.columns:
            scaled[column] = pd.to_numeric(scaled[column], errors="coerce") / 1e9
    return scaled


def _validate_exact_panel(frame: pd.DataFrame, require_complete: bool) -> None:
    standard = frame[frame["reform_name"].isin(STANDARD_REFORMS)].copy()
    standard["year"] = standard["year"].astype(int)
    duplicates = standard.duplicated(["reform_name", "year"], keep=False)
    if bool(duplicates.any()):
        raise ValueError(
            "Duplicate full-H5 aggregate rows:\n"
            + standard.loc[duplicates, ["reform_name", "year"]].to_string(index=False)
        )

    missing: list[tuple[str, int]] = []
    for reform in STANDARD_REFORMS:
        years = set(standard.loc[standard["reform_name"] == reform, "year"].astype(int))
        for year in REQUIRED_EXACT_YEARS:
            if year not in years:
                missing.append((reform, year))

    if require_complete and missing:
        preview = ", ".join(f"{reform}:{year}" for reform, year in missing[:20])
        raise ValueError(
            f"Missing {len(missing)} selected full-H5 cells; first missing: {preview}"
        )


def _interpolate_standard_reform(group: pd.DataFrame) -> pd.DataFrame:
    reform_name = str(group["reform_name"].iloc[0])
    group = group.sort_values("year").drop_duplicates("year", keep="last")
    group = group.set_index("year")
    annual = pd.DataFrame(index=pd.Index(ANNUAL_YEARS, name="year"))
    merged = annual.join(group, how="left")
    merged["reform_name"] = reform_name
    merged["scoring_type"] = "static"

    numeric_columns = [column for column in DOLLAR_COLUMNS if column in merged.columns]
    for column in numeric_columns:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").interpolate(
            method="index",
            limit_area="inside",
        )

    exact_years = set(group.index.astype(int))
    merged["full_h5_result_type"] = [
        "exact_full_h5"
        if year in exact_years
        else "linear_interpolation_between_full_h5_years"
        for year in merged.index.astype(int)
    ]
    merged["source"] = merged["full_h5_result_type"]
    merged = merged.reset_index()
    return merged


def _annual_display_from_exact(exact: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for reform in STANDARD_REFORMS:
        group = exact[exact["reform_name"] == reform].copy()
        if group.empty:
            continue
        rows.append(_interpolate_standard_reform(group))
    if not rows:
        return pd.DataFrame(
            columns=[*DASHBOARD_COLUMNS, "full_h5_result_type", "source"]
        )
    return pd.concat(rows, ignore_index=True)


def publish_full_h5_static_results(
    *,
    full_h5_aggregate_path: Path,
    reference_static_path: Path,
    tob_baseline_path: Path,
    exact_output_path: Path,
    display_output_path: Path,
    metadata_output_path: Path,
    require_complete: bool,
) -> dict[str, Any]:
    aggregate = pd.read_csv(full_h5_aggregate_path)
    _validate_exact_panel(aggregate, require_complete=require_complete)
    exact = _scale_dollars_to_billions(aggregate)
    exact["full_h5_result_type"] = "exact_full_h5"
    exact["baseline_source"] = EXACT_BASELINE_SOURCE

    annual_standard = _annual_display_from_exact(exact)
    combined = annual_standard.copy()
    combined = combined.sort_values(["reform_name", "year"]).reset_index(drop=True)

    exact_output_path.parent.mkdir(parents=True, exist_ok=True)
    display_output_path.parent.mkdir(parents=True, exist_ok=True)
    exact.to_csv(exact_output_path, index=False, float_format="%.12g")
    combined.to_csv(display_output_path, index=False, float_format="%.12g")

    exact_standard = exact[exact["reform_name"].isin(STANDARD_REFORMS)]
    metadata = {
        "schema": "crfb_full_h5_static_dashboard_publication/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "full_h5_aggregate_path": str(full_h5_aggregate_path),
        "reference_static_path": str(reference_static_path),
        "exact_output_path": str(exact_output_path),
        "display_output_path": str(display_output_path),
        "post_obbba_tob_baseline_applied": False,
        "standard_reforms": list(STANDARD_REFORMS),
        "excluded_non_contract_rows": True,
        "exclusion_reason": (
            "Only current-contract full-H5 selected-panel rows are public. "
            "Rows from earlier non-contract releases are intentionally excluded."
        ),
        "required_exact_years": list(REQUIRED_EXACT_YEARS),
        "annual_display_years": list(ANNUAL_YEARS),
        "expected_exact_cell_count": EXPECTED_EXACT_CELL_COUNT,
        "exact_standard_cell_count": int(len(exact_standard)),
        "dashboard_row_count": int(len(combined)),
        "dashboard_standard_exact_rows": int(
            (combined["full_h5_result_type"] == "exact_full_h5").sum()
        ),
        "dashboard_standard_interpolated_rows": int(
            (
                combined["full_h5_result_type"]
                == "linear_interpolation_between_full_h5_years"
            ).sum()
        ),
        "manual_weight_aggregation_used": False,
        "unit_conversion": "input dollars divided by 1e9 for dashboard billions",
        "tob_calibration": (
            "Not applied. results.csv keeps microsimulation aggregates unadulterated; "
            "interpolated rows are marked separately in full_h5_result_type/source."
        ),
        "baseline_revenue_source": (
            "baseline_revenue comes from the full-H5 microsimulation aggregate. "
            "No reference baseline substitution, display normalization, or TOB "
            "baseline calibration is applied."
        ),
        "long_horizon_display_policy": (
            "All fourteen reforms use exact full-H5 microsimulation outputs "
            "for 2026, 2030, and every fifth year from 2035 to 2100 on the "
            "populace baselines. Non-modeled annual display rows are "
            "linearly interpolated only for dashboard continuity."
        ),
    }
    metadata_output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_output_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-h5-aggregate", type=Path, default=DEFAULT_FULL_H5_AGGREGATE
    )
    parser.add_argument(
        "--reference-static",
        type=Path,
        default=DEFAULT_REFERENCE_STATIC,
    )
    parser.add_argument("--tob-baseline", type=Path, default=DEFAULT_TOB_BASELINE)
    parser.add_argument("--exact-output", type=Path, default=DEFAULT_EXACT_OUTPUT)
    parser.add_argument("--display-output", type=Path, default=DEFAULT_DISPLAY_OUTPUT)
    parser.add_argument("--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT)
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata = publish_full_h5_static_results(
        full_h5_aggregate_path=args.full_h5_aggregate,
        reference_static_path=args.reference_static,
        tob_baseline_path=args.tob_baseline,
        exact_output_path=args.exact_output,
        display_output_path=args.display_output,
        metadata_output_path=args.metadata_output,
        require_complete=not args.allow_incomplete,
    )
    print(
        "Published dashboard static results with "
        f"{metadata['exact_standard_cell_count']}/"
        f"{metadata['expected_exact_cell_count']} exact full-H5 cells and "
        f"{metadata['dashboard_standard_interpolated_rows']} interpolated "
        "standard-option display rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
