# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.publish_full_h5_static_dashboard_results import (
    ANNUAL_YEARS,
    DASHBOARD_COLUMNS,
    STANDARD_REFORMS,
    _scale_dollars_to_billions,
)


RESULTS = REPO / "results"
DEFAULT_BEHAVIORAL_ENDPOINT_AGGREGATE = (
    RESULTS
    / "modal_runs_production"
    / "full_h5_5a35713_behavioral_endpoints_20260522.csv"
)
DEFAULT_STATIC_DISPLAY = (
    RESULTS / "all_static_results_full_h5_selected_panel_display_20260522.csv"
)
DEFAULT_TOB_BASELINE = REPO / "data" / "ssa_tob_baseline_75year.csv"
DEFAULT_BEHAVIORAL_EXACT_OUTPUT = (
    RESULTS / "behavioral_endpoint_full_h5_exact_20260522.csv"
)
DEFAULT_BEHAVIORAL_DISPLAY_OUTPUT = (
    RESULTS / "behavioral_endpoint_ratio_display_20260522.csv"
)
DEFAULT_METADATA_OUTPUT = (
    RESULTS / "behavioral_endpoint_ratio_display_20260522_metadata.json"
)

ENDPOINT_YEARS = (2026, 2100)
IMPACT_RATIO_COLUMNS = (
    "revenue_impact",
    "tob_medicare_hi_impact",
    "tob_oasdi_impact",
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
BASELINE_COLUMNS = (
    "baseline_revenue",
    "baseline_tob_medicare_hi",
    "baseline_tob_oasdi",
    "baseline_tob_total",
)
REFORM_LEVEL_COLUMNS = {
    "reform_revenue": ("baseline_revenue", "revenue_impact"),
    "reform_tob_medicare_hi": (
        "baseline_tob_medicare_hi",
        "tob_medicare_hi_impact",
    ),
    "reform_tob_oasdi": ("baseline_tob_oasdi", "tob_oasdi_impact"),
    "reform_tob_total": ("baseline_tob_total", "tob_total_impact"),
}


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO))
    except ValueError:
        return str(resolved)


def _validate_endpoint_panel(frame: pd.DataFrame) -> None:
    standard = frame[frame["reform_name"].isin(STANDARD_REFORMS)].copy()
    standard["year"] = standard["year"].astype(int)
    duplicates = standard.duplicated(["reform_name", "year"], keep=False)
    if bool(duplicates.any()):
        raise ValueError(
            "Duplicate behavioral endpoint rows:\n"
            + standard.loc[duplicates, ["reform_name", "year"]].to_string(index=False)
        )

    missing: list[tuple[str, int]] = []
    for reform in STANDARD_REFORMS:
        years = set(
            standard.loc[standard["reform_name"] == reform, "year"].astype(int)
        )
        for year in ENDPOINT_YEARS:
            if year not in years:
                missing.append((reform, year))
    if missing:
        preview = ", ".join(f"{reform}:{year}" for reform, year in missing[:20])
        raise ValueError(
            f"Missing {len(missing)} behavioral endpoint cells; first missing: {preview}"
        )


def _published_behavioral_endpoints(
    endpoint_aggregate: pd.DataFrame,
    *,
    static_display_path: Path,
    tob_baseline_path: Path,
) -> pd.DataFrame:
    exact = endpoint_aggregate.copy()
    exact = exact[exact["reform_name"].isin(STANDARD_REFORMS)].copy()
    exact["year"] = exact["year"].astype(int)
    exact = exact[exact["year"].isin(ENDPOINT_YEARS)].copy()
    _validate_endpoint_panel(exact)

    exact = _scale_dollars_to_billions(exact)
    exact["scoring_type"] = "behavioral"
    exact["source"] = "exact_behavioral_endpoint_full_h5"
    exact["full_h5_result_type"] = "exact_behavioral_endpoint_full_h5"
    return exact.sort_values(["reform_name", "year"]).reset_index(drop=True)


def _endpoint_ratio(
    *,
    behavioral_value: float,
    static_value: float,
    fallback_records: list[dict[str, Any]],
    reform_name: str,
    year: int,
    column: str,
) -> float:
    if abs(static_value) > 1e-9:
        return behavioral_value / static_value
    if abs(behavioral_value) <= 1e-9:
        return 1.0
    fallback_records.append(
        {
            "reform_name": reform_name,
            "year": int(year),
            "column": column,
            "static_value": static_value,
            "behavioral_value": behavioral_value,
            "method": "endpoint_absolute_value_fallback",
        }
    )
    return float("nan")


def _interpolate_ratio(start: float, end: float, year: int) -> float:
    span = ENDPOINT_YEARS[1] - ENDPOINT_YEARS[0]
    weight = (year - ENDPOINT_YEARS[0]) / span
    return start + (end - start) * weight


def _behavioral_annual_for_reform(
    *,
    reform_name: str,
    static_group: pd.DataFrame,
    endpoint_group: pd.DataFrame,
    fallback_records: list[dict[str, Any]],
) -> pd.DataFrame:
    static_group = static_group.sort_values("year").set_index("year")
    endpoint_group = endpoint_group.sort_values("year").set_index("year")
    rows: list[dict[str, Any]] = []

    for year in ANNUAL_YEARS:
        static_row = static_group.loc[year].to_dict()
        row = dict(static_row)
        row["reform_name"] = reform_name
        row["year"] = int(year)
        row["scoring_type"] = "behavioral"

        for column in BASELINE_COLUMNS:
            if column in static_row:
                row[column] = float(static_row[column])

        for column in IMPACT_RATIO_COLUMNS:
            if column not in static_group.columns or column not in endpoint_group.columns:
                continue
            endpoint_ratios: dict[int, float] = {}
            endpoint_values: dict[int, float] = {}
            for endpoint_year in ENDPOINT_YEARS:
                static_value = float(static_group.loc[endpoint_year, column])
                behavioral_value = float(endpoint_group.loc[endpoint_year, column])
                endpoint_values[endpoint_year] = behavioral_value
                endpoint_ratios[endpoint_year] = _endpoint_ratio(
                    behavioral_value=behavioral_value,
                    static_value=static_value,
                    fallback_records=fallback_records,
                    reform_name=reform_name,
                    year=endpoint_year,
                    column=column,
                )

            if year in ENDPOINT_YEARS:
                row[column] = endpoint_values[year]
            elif any(pd.isna(value) for value in endpoint_ratios.values()):
                row[column] = _interpolate_ratio(
                    endpoint_values[ENDPOINT_YEARS[0]],
                    endpoint_values[ENDPOINT_YEARS[1]],
                    year,
                )
            else:
                ratio = _interpolate_ratio(
                    endpoint_ratios[ENDPOINT_YEARS[0]],
                    endpoint_ratios[ENDPOINT_YEARS[1]],
                    year,
                )
                row[column] = float(static_row[column]) * ratio

        for reform_column, (baseline_column, impact_column) in REFORM_LEVEL_COLUMNS.items():
            if baseline_column in row and impact_column in row:
                row[reform_column] = float(row[baseline_column]) + float(
                    row[impact_column]
                )

        if year in ENDPOINT_YEARS:
            endpoint_row = endpoint_group.loc[year].to_dict()
            for column in (
                "scenario_h5_uri",
                "metadata_uri",
                "complete_uri",
                "output_h5_sha256",
                "run_prefix",
                "baseline_source",
            ):
                row[column] = endpoint_row.get(column, "")
            row["source"] = "exact_behavioral_endpoint_full_h5"
            row["full_h5_result_type"] = "exact_behavioral_endpoint_full_h5"
        else:
            for column in (
                "scenario_h5_uri",
                "metadata_uri",
                "complete_uri",
                "output_h5_sha256",
            ):
                row[column] = ""
            row["run_prefix"] = "behavioral_endpoint_ratio_interpolation_20260522"
            row["baseline_source"] = "static_display_baseline"
            row["source"] = "linear_interpolation_between_behavioral_endpoint_ratios"
            row["full_h5_result_type"] = (
                "linear_interpolation_between_behavioral_endpoint_ratios"
            )
        rows.append(row)

    return pd.DataFrame(rows)


def build_behavioral_display(
    *,
    endpoint_aggregate_path: Path,
    static_display_path: Path,
    tob_baseline_path: Path,
    exact_output_path: Path,
    display_output_path: Path,
    metadata_output_path: Path,
) -> dict[str, Any]:
    endpoint_aggregate = pd.read_csv(endpoint_aggregate_path)
    exact = _published_behavioral_endpoints(
        endpoint_aggregate,
        static_display_path=static_display_path,
        tob_baseline_path=tob_baseline_path,
    )
    static = pd.read_csv(static_display_path)
    static = static[static["reform_name"].isin(STANDARD_REFORMS)].copy()
    static["year"] = static["year"].astype(int)

    missing_static: list[tuple[str, int]] = []
    for reform in STANDARD_REFORMS:
        years = set(static.loc[static["reform_name"] == reform, "year"].astype(int))
        for year in ANNUAL_YEARS:
            if year not in years:
                missing_static.append((reform, year))
    if missing_static:
        preview = ", ".join(
            f"{reform}:{year}" for reform, year in missing_static[:20]
        )
        raise ValueError(f"Missing static display rows; first missing: {preview}")

    fallback_records: list[dict[str, Any]] = []
    annual_rows: list[pd.DataFrame] = []
    for reform in STANDARD_REFORMS:
        annual_rows.append(
            _behavioral_annual_for_reform(
                reform_name=reform,
                static_group=static[static["reform_name"] == reform],
                endpoint_group=exact[exact["reform_name"] == reform],
                fallback_records=fallback_records,
            )
        )

    display = pd.concat(annual_rows, ignore_index=True)
    columns = list(dict.fromkeys([*DASHBOARD_COLUMNS, *static.columns, *display.columns]))
    exact = exact.reindex(columns=columns)
    display = display.reindex(columns=columns)
    exact_output_path.parent.mkdir(parents=True, exist_ok=True)
    display_output_path.parent.mkdir(parents=True, exist_ok=True)
    exact.to_csv(exact_output_path, index=False, float_format="%.12g")
    display.to_csv(display_output_path, index=False, float_format="%.12g")

    metadata = {
        "schema": "crfb_behavioral_endpoint_ratio_publication/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "endpoint_aggregate_path": _display_path(endpoint_aggregate_path),
        "static_display_path": _display_path(static_display_path),
        "exact_output_path": _display_path(exact_output_path),
        "display_output_path": _display_path(display_output_path),
        "post_obbba_tob_baseline_applied": False,
        "standard_reforms": list(STANDARD_REFORMS),
        "endpoint_years": list(ENDPOINT_YEARS),
        "annual_display_years": list(ANNUAL_YEARS),
        "exact_endpoint_rows": int(len(exact)),
        "dashboard_row_count": int(len(display)),
        "dashboard_exact_endpoint_rows": int(
            (display["full_h5_result_type"] == "exact_behavioral_endpoint_full_h5").sum()
        ),
        "dashboard_interpolated_rows": int(
            (
                display["full_h5_result_type"]
                == "linear_interpolation_between_behavioral_endpoint_ratios"
            ).sum()
        ),
        "interpolation_method": (
            "For each reform and impact metric, compute behavioral/static ratios "
            "at 2026 and 2100 exact full-H5 endpoints, linearly interpolate the "
            "ratio by year, and multiply the static annual row by that ratio. "
            "Baseline levels are copied from the static current-law baseline."
        ),
        "zero_static_denominator_fallbacks": fallback_records,
        "manual_weight_aggregation_used": False,
        "legacy_aggregate_sources_used": False,
        "tob_calibration": (
            "Not applied. Behavioral endpoint rows use full-H5 microsimulation "
            "aggregates, with non-endpoint years derived only by the documented "
            "behavioral/static ratio interpolation."
        ),
    }
    metadata_output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_output_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Publish annual behavioral rows from exact 2026/2100 full-H5 "
            "endpoint aggregates and static annual ratios."
        )
    )
    parser.add_argument(
        "--endpoint-aggregate",
        type=Path,
        default=DEFAULT_BEHAVIORAL_ENDPOINT_AGGREGATE,
    )
    parser.add_argument(
        "--static-display",
        type=Path,
        default=DEFAULT_STATIC_DISPLAY,
    )
    parser.add_argument("--tob-baseline", type=Path, default=DEFAULT_TOB_BASELINE)
    parser.add_argument(
        "--exact-output",
        type=Path,
        default=DEFAULT_BEHAVIORAL_EXACT_OUTPUT,
    )
    parser.add_argument(
        "--display-output",
        type=Path,
        default=DEFAULT_BEHAVIORAL_DISPLAY_OUTPUT,
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=DEFAULT_METADATA_OUTPUT,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata = build_behavioral_display(
        endpoint_aggregate_path=args.endpoint_aggregate,
        static_display_path=args.static_display,
        tob_baseline_path=args.tob_baseline,
        exact_output_path=args.exact_output,
        display_output_path=args.display_output,
        metadata_output_path=args.metadata_output,
    )
    print(
        "Published behavioral endpoint-ratio rows with "
        f"{metadata['exact_endpoint_rows']} exact endpoints and "
        f"{metadata['dashboard_interpolated_rows']} interpolated rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
