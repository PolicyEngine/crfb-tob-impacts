from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from runtime_config import dataset_path, load_dataset_metadata
from tax_assumption_loader import DEFAULT_TAX_ASSUMPTION_FACTORY


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-option13-dir", type=Path, required=True)
    parser.add_argument("--source-option14-dir", type=Path, required=True)
    parser.add_argument("--endpoint-option13", type=Path, required=True)
    parser.add_argument("--endpoint-option14", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--policy-start-year", type=int, default=2035)
    parser.add_argument(
        "--tax-assumption-factory",
        default=DEFAULT_TAX_ASSUMPTION_FACTORY,
    )
    parser.add_argument("--tax-assumption-start-year", type=int, default=2035)
    parser.add_argument("--tax-assumption-end-year", type=int, default=2100)
    parser.add_argument("--option14-comparison-baseline", default="balanced_fix")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def marker_value(row: dict, key: str) -> object | None:
    value = row.get(key)
    if value is None or pd.isna(value):
        return None
    return value


def set_marker(row: dict, key: str, value: object) -> None:
    existing = marker_value(row, key)
    if existing is not None and str(existing).strip() != str(value):
        raise ValueError(
            f"Existing {key}={existing!r} conflicts with expected {value!r}"
        )
    row[key] = value


def truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if value is None or pd.isna(value):
        return False
    return bool(value)


def enrich_row(
    row: dict,
    *,
    year: int,
    run_id: str,
    policy_start_year: int,
    tax_assumption_factory: str,
    tax_assumption_start_year: int,
    tax_assumption_end_year: int,
    comparison_baseline: str,
    stacked_reform: bool = False,
) -> dict:
    dataset = Path(dataset_path(year))
    metadata_path = Path(f"{dataset}.metadata.json")
    metadata = load_dataset_metadata(dataset)
    row = dict(row)
    set_marker(row, "tax_assumption_factory", tax_assumption_factory)
    set_marker(row, "tax_assumption_start_year", tax_assumption_start_year)
    set_marker(row, "tax_assumption_end_year", tax_assumption_end_year)
    set_marker(row, "comparison_baseline", comparison_baseline)
    if stacked_reform:
        existing = marker_value(row, "stacked_reform")
        if existing is not None and not truthy(existing):
            raise ValueError(
                f"Existing stacked_reform={existing!r} conflicts with expected True"
            )
        row["stacked_reform"] = True
    row["special_case_run_id"] = run_id
    row["dataset_file"] = str(dataset)
    row["dataset_metadata_file"] = str(metadata_path)
    row["dataset_metadata_sha256"] = sha256_file(metadata_path)
    row["calibration_quality"] = metadata.get("calibration_audit", {}).get(
        "calibration_quality"
    )
    row["calibration_profile"] = metadata.get("profile", {}).get("name")
    row["target_source_name"] = metadata.get("target_source", {}).get("name")
    row["tax_assumption_name"] = metadata.get("tax_assumption", {}).get("name")
    row["policy_start_year"] = policy_start_year
    return row


def rewrite_with_provenance(
    source_csv: Path,
    dest_csv: Path,
    *,
    year: int,
    run_id: str,
    policy_start_year: int,
    tax_assumption_factory: str,
    tax_assumption_start_year: int,
    tax_assumption_end_year: int,
    comparison_baseline: str,
    stacked_reform: bool = False,
) -> None:
    row = pd.read_csv(source_csv).iloc[0].to_dict()
    enriched = enrich_row(
        row,
        year=year,
        run_id=run_id,
        policy_start_year=policy_start_year,
        tax_assumption_factory=tax_assumption_factory,
        tax_assumption_start_year=tax_assumption_start_year,
        tax_assumption_end_year=tax_assumption_end_year,
        comparison_baseline=comparison_baseline,
        stacked_reform=stacked_reform,
    )
    dest_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([enriched]).to_csv(dest_csv, index=False)


def main() -> None:
    args = parse_args()
    option13_out = args.output_root / "option13"
    option14_out = args.output_root / "option14"
    option13_out.mkdir(parents=True, exist_ok=True)
    option14_out.mkdir(parents=True, exist_ok=True)

    copied_years: list[int] = []

    for year in range(args.policy_start_year, 2100):
        rewrite_with_provenance(
            args.source_option13_dir / f"{year}_static_results.csv",
            option13_out / f"{year}_static_results.csv",
            year=year,
            run_id=args.run_id,
            policy_start_year=args.policy_start_year,
            tax_assumption_factory=args.tax_assumption_factory,
            tax_assumption_start_year=args.tax_assumption_start_year,
            tax_assumption_end_year=args.tax_assumption_end_year,
            comparison_baseline="current_law",
        )
        rewrite_with_provenance(
            args.source_option14_dir / f"{year}_static_results.csv",
            option14_out / f"{year}_static_results.csv",
            year=year,
            run_id=args.run_id,
            policy_start_year=args.policy_start_year,
            tax_assumption_factory=args.tax_assumption_factory,
            tax_assumption_start_year=args.tax_assumption_start_year,
            tax_assumption_end_year=args.tax_assumption_end_year,
            comparison_baseline=args.option14_comparison_baseline,
            stacked_reform=True,
        )
        copied_years.append(year)

    rewrite_with_provenance(
        args.endpoint_option13,
        option13_out / "2100_static_results.csv",
        year=2100,
        run_id=args.run_id,
        policy_start_year=args.policy_start_year,
        tax_assumption_factory=args.tax_assumption_factory,
        tax_assumption_start_year=args.tax_assumption_start_year,
        tax_assumption_end_year=args.tax_assumption_end_year,
        comparison_baseline="current_law",
    )
    rewrite_with_provenance(
        args.endpoint_option14,
        option14_out / "2100_static_results.csv",
        year=2100,
        run_id=args.run_id,
        policy_start_year=args.policy_start_year,
        tax_assumption_factory=args.tax_assumption_factory,
        tax_assumption_start_year=args.tax_assumption_start_year,
        tax_assumption_end_year=args.tax_assumption_end_year,
        comparison_baseline=args.option14_comparison_baseline,
        stacked_reform=True,
    )
    copied_years.append(2100)

    manifest = {
        "run_id": args.run_id,
        "policy_start_year": args.policy_start_year,
        "tax_assumption_factory": args.tax_assumption_factory,
        "tax_assumption_start_year": args.tax_assumption_start_year,
        "tax_assumption_end_year": args.tax_assumption_end_year,
        "option14_comparison_baseline": args.option14_comparison_baseline,
        "option14_stacked_reform": True,
        "option13_dir": str(option13_out),
        "option14_dir": str(option14_out),
        "source_option13_dir": str(args.source_option13_dir),
        "source_option14_dir": str(args.source_option14_dir),
        "endpoint_option13": str(args.endpoint_option13),
        "endpoint_option14": str(args.endpoint_option14),
        "years": copied_years,
        "notes": [
            "2035-2099 copied from existing latest-HF special-case raws and enriched with dataset provenance.",
            "2100 overwritten from corrected local rerun using extrapolated HI Trustees endpoint.",
        ],
    }
    (args.output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"Wrote {option13_out}")
    print(f"Wrote {option14_out}")
    print(f"Wrote {args.output_root / 'manifest.json'}")


if __name__ == "__main__":
    main()
