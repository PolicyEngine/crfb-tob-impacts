"""Publish additive balanced-fix results for the dashboard.

The canonical current-law panel remains ``results.csv``. This script consumes
exact balanced-fix anchor rows recovered from Modal, interpolates the
solvent/current-law ratio between anchors, and writes a separate public file
for the "SS solvent" baseline scenario.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import glob
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.balanced_fix import (
    BALANCED_FIX_ANCHOR_YEARS,
    BALANCED_FIX_PUBLISH_ANCHOR_YEARS,
    BALANCED_FIX_REFORMS,
    BALANCED_FIX_SPOT_CHECK_YEARS,
)
from src.trust_fund_allocation import split_revenue_impacts


REPO = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = REPO / "results.csv"
DEFAULT_ANCHOR_GLOBS = (
    "tmp/balanced_fix_r2fix_*/[0-9][0-9][0-9][0-9].csv",
    "tmp/balanced_fix_recovered/[0-9][0-9][0-9][0-9].csv",
)
DEFAULT_OUTPUTS = (
    REPO / "results" / "modal_runs_production" / "balanced_fix_results.csv",
    REPO / "dashboard" / "public" / "data" / "balanced_fix_results.csv",
)
DEFAULT_METADATA_OUTPUTS = (
    REPO / "results" / "modal_runs_production" / "balanced_fix_results_metadata.json",
    REPO / "dashboard" / "public" / "data" / "balanced_fix_results_metadata.json",
)
DEFAULT_RUN_PREFIX = "balanced_fix_v2pop_tr2026_endpoints_first_20260619_hi2100fix"
NEAR_ZERO_BILLIONS = 0.001

VALUE_COLUMNS = (
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
    "solvent_oasdi_impact",
    "solvent_medicare_hi_impact",
    "solvent_general_fund_impact",
)

INTERPOLATED_RATIO_COLUMNS = (
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish additive balanced-fix dashboard rows."
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=DEFAULT_RESULTS,
        help="Current-law dashboard results.csv used as the ratio base.",
    )
    parser.add_argument(
        "--anchor-csv",
        type=Path,
        action="append",
        default=[],
        help="Exact balanced-fix year CSV recovered from Modal. Repeatable.",
    )
    parser.add_argument(
        "--anchor-glob",
        action="append",
        default=[],
        help="Glob for exact balanced-fix year CSVs. Defaults to known tmp paths.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        action="append",
        default=[],
        help="CSV output path. Repeatable.",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        action="append",
        default=[],
        help="Metadata JSON output path. Repeatable.",
    )
    parser.add_argument("--run-prefix", default=DEFAULT_RUN_PREFIX)
    return parser.parse_args()


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ratio(numerator: float, denominator: float) -> float:
    if abs(denominator) < NEAR_ZERO_BILLIONS:
        return 1.0 if abs(numerator) < NEAR_ZERO_BILLIONS else 0.0
    return numerator / denominator


def _interpolate(
    left: float, right: float, year: int, left_year: int, right_year: int
) -> float:
    if left_year == right_year:
        return left
    weight = (year - left_year) / (right_year - left_year)
    return left * (1 - weight) + right * weight


def discover_anchor_paths(
    anchor_csvs: list[Path], anchor_globs: list[str]
) -> list[Path]:
    paths = {path.resolve() for path in anchor_csvs}
    globs = anchor_globs or list(DEFAULT_ANCHOR_GLOBS)
    for pattern in globs:
        paths.update(Path(path).resolve() for path in glob.glob(str(REPO / pattern)))
    return sorted(paths)


def load_anchor_rows(anchor_paths: list[Path]) -> pd.DataFrame:
    if not anchor_paths:
        raise FileNotFoundError("No balanced-fix anchor CSVs found.")

    frames = []
    for path in anchor_paths:
        frame = pd.read_csv(path)
        frame["anchor_source_path"] = str(
            path.relative_to(REPO) if path.is_relative_to(REPO) else path
        )
        frame["anchor_source_sha256"] = file_sha256(path)
        frames.append(frame)

    anchors = pd.concat(frames, ignore_index=True)
    anchors["year"] = anchors["year"].astype(int)
    anchors["reform_name"] = anchors["reform_name"].astype(str)
    anchors = anchors[anchors["year"].isin(BALANCED_FIX_PUBLISH_ANCHOR_YEARS)].copy()
    anchors = anchors.drop_duplicates(["reform_name", "year"], keep="last")

    required = {
        (reform, year)
        for reform in BALANCED_FIX_REFORMS
        for year in BALANCED_FIX_PUBLISH_ANCHOR_YEARS
    }
    present = set(zip(anchors["reform_name"], anchors["year"], strict=False))
    missing = sorted(required - present)
    if missing:
        raise RuntimeError(f"Missing balanced-fix anchor rows: {missing}")
    return anchors


def current_law_default_rows(results: pd.DataFrame) -> pd.DataFrame:
    rows = results[
        results["scoring_type"].astype(str).eq("static")
        & results["reform_name"].astype(str).isin(BALANCED_FIX_REFORMS)
        & results["year"]
        .astype(int)
        .between(
            min(BALANCED_FIX_ANCHOR_YEARS),
            max(BALANCED_FIX_ANCHOR_YEARS),
        )
    ].copy()
    if rows.empty:
        raise RuntimeError("No current-law static rows found for balanced-fix reforms.")

    split_values = rows.apply(
        lambda row: split_revenue_impacts(row, allocation_mode="baselineShares"),
        axis=1,
        result_type="expand",
    )
    rows["solvent_oasdi_impact"] = split_values[1]
    rows["solvent_medicare_hi_impact"] = split_values[2]
    rows["solvent_general_fund_impact"] = (
        rows["revenue_impact"] - split_values[1] - split_values[2]
    )
    return rows


def anchor_ratio_map(
    anchors: pd.DataFrame, current_law: pd.DataFrame
) -> dict[tuple[str, int, str], float]:
    current_indexed = current_law.set_index(["reform_name", "year"])
    ratios: dict[tuple[str, int, str], float] = {}
    for anchor in anchors.to_dict("records"):
        key = (str(anchor["reform_name"]), int(anchor["year"]))
        current = current_indexed.loc[key]
        for column in (
            *INTERPOLATED_RATIO_COLUMNS,
            "solvent_oasdi_impact",
            "solvent_medicare_hi_impact",
        ):
            ratios[(key[0], key[1], column)] = _ratio(
                _as_float(anchor.get(column)),
                _as_float(current.get(column)),
            )
    return ratios


def surrounding_anchor_years(year: int) -> tuple[int, int]:
    anchors = tuple(BALANCED_FIX_PUBLISH_ANCHOR_YEARS)
    if year in anchors:
        return year, year
    for left, right in zip(anchors, anchors[1:], strict=False):
        if left < year < right:
            return left, right
    raise ValueError(f"Year {year} is outside balanced-fix anchor range.")


def build_balanced_fix_results(
    anchors: pd.DataFrame, current_law: pd.DataFrame
) -> pd.DataFrame:
    anchor_lookup = anchors.set_index(["reform_name", "year"])
    rows: list[dict[str, Any]] = []

    for current in current_law.sort_values(["reform_name", "year"]).to_dict("records"):
        reform = str(current["reform_name"])
        year = int(current["year"])
        left_year, right_year = surrounding_anchor_years(year)
        exact_key = (reform, year)

        if exact_key in anchor_lookup.index:
            row = dict(anchor_lookup.loc[exact_key])
            row["reform_name"] = reform
            row["year"] = year
            row["balanced_fix_result_type"] = "exact_solvent_baseline_full_h5"
            row["interpolation_left_year"] = year
            row["interpolation_right_year"] = year
        else:
            # Linearly interpolate the real solvent anchor rows directly. The
            # earlier method scaled the current-law row by an interpolated
            # solvent/current-law ratio; that ratio divides by the current-law
            # value, so it exploded wherever current law crosses zero (option12's
            # phased-out benefit tax produced a spurious crater at 2055/2060) and
            # broke the revenue_impact = reform - baseline identity. Interpolating
            # the anchors directly is artifact-free and internally consistent.
            left_row = anchor_lookup.loc[(reform, left_year)]
            right_row = anchor_lookup.loc[(reform, right_year)]
            row = dict(current)
            row["solvent_baseline"] = "ss_solvent"
            for column in VALUE_COLUMNS:
                row[column] = _interpolate(
                    _as_float(left_row.get(column)),
                    _as_float(right_row.get(column)),
                    year,
                    left_year,
                    right_year,
                )
            row["anchor_source_path"] = ""
            row["anchor_source_sha256"] = ""
            row["balanced_fix_result_type"] = (
                "linear_interpolation_between_solvent_baseline_anchors"
            )
            row["interpolation_left_year"] = left_year
            row["interpolation_right_year"] = right_year

        row["baseline_scenario"] = "ss_solvent"
        row["source"] = row["balanced_fix_result_type"]
        rows.append(row)

    result = pd.DataFrame(rows)
    result["year"] = result["year"].astype(int)
    result = result.sort_values(["reform_name", "year"]).reset_index(drop=True)

    split_total = (
        result["solvent_oasdi_impact"]
        + result["solvent_medicare_hi_impact"]
        + result["solvent_general_fund_impact"]
    )
    drift = (split_total - result["revenue_impact"]).abs().max()
    if drift > 1e-8:
        raise AssertionError(f"Balanced-fix split drift exceeds tolerance: {drift}")
    return result


def metadata_for(
    result: pd.DataFrame,
    anchor_paths: list[Path],
    run_prefix: str,
    current_law_results: Path,
) -> dict[str, Any]:
    return {
        "schema": "crfb_balanced_fix_public_results/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_prefix": run_prefix,
        "baseline_scenario": "ss_solvent",
        "current_law_results": str(
            current_law_results.relative_to(REPO)
            if current_law_results.is_relative_to(REPO)
            else current_law_results
        ),
        "planned_anchor_years": list(BALANCED_FIX_ANCHOR_YEARS),
        "promoted_spot_check_years": list(BALANCED_FIX_SPOT_CHECK_YEARS),
        "anchor_years": list(BALANCED_FIX_PUBLISH_ANCHOR_YEARS),
        "reforms": list(BALANCED_FIX_REFORMS),
        "year_start": int(result["year"].min()),
        "year_end": int(result["year"].max()),
        "rows": int(len(result)),
        "exact_rows": int(
            result["balanced_fix_result_type"]
            .eq("exact_solvent_baseline_full_h5")
            .sum()
        ),
        "interpolated_rows": int(
            result["balanced_fix_result_type"]
            .eq("linear_interpolation_between_solvent_baseline_anchor_ratios")
            .sum()
        ),
        "interpolation_method": (
            "For each reform and metric, compute the solvent/current-law ratio "
            "at exact anchor years 2035, 2050, 2065, 2075, and 2100; "
            "linearly interpolate that ratio by year; multiply the live "
            "current-law static row by the interpolated ratio. 2065 was "
            "promoted from validation spot-check to exact anchor because "
            "the direct option12 split materially differed from the "
            "2035/2050/2075/2100-only interpolation."
        ),
        "split_contract": (
            "solvent_oasdi_impact + solvent_medicare_hi_impact + "
            "solvent_general_fund_impact equals revenue_impact for every row."
        ),
        "anchor_sources": [
            {
                "path": str(
                    path.relative_to(REPO) if path.is_relative_to(REPO) else path
                ),
                "sha256": file_sha256(path),
            }
            for path in anchor_paths
        ],
    }


def write_outputs(
    result: pd.DataFrame,
    metadata: dict[str, Any],
    outputs: list[Path],
    metadata_outputs: list[Path],
) -> None:
    for output in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output, index=False, float_format="%.10f")
    for output in metadata_outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def main() -> int:
    args = parse_args()
    anchor_paths = discover_anchor_paths(args.anchor_csv, args.anchor_glob)
    anchors = load_anchor_rows(anchor_paths)
    current_law = current_law_default_rows(pd.read_csv(args.results))
    result = build_balanced_fix_results(anchors, current_law)
    metadata = metadata_for(
        result, anchor_paths, args.run_prefix, args.results.resolve()
    )
    outputs = args.output or list(DEFAULT_OUTPUTS)
    metadata_outputs = args.metadata_output or list(DEFAULT_METADATA_OUTPUTS)
    write_outputs(result, metadata, outputs, metadata_outputs)
    print(
        "Published balanced-fix results: "
        f"{len(result)} rows, {metadata['exact_rows']} exact, "
        f"{metadata['interpolated_rows']} interpolated."
    )
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
