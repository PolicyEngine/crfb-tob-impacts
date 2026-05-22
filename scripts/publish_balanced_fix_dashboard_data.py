from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO / "results" / "option13_results.csv"
DEFAULT_RECOVERED_DIR = (
    REPO
    / "results"
    / "recovered_special_case_runs"
    / "balanced_fix_5a35713_option13_full_h5_selected_panel_20260522_115108"
)
DEFAULT_OUTPUT = REPO / "dashboard" / "public" / "data" / "balanced_fix_baseline.csv"
DEFAULT_METADATA_OUTPUT = (
    REPO / "dashboard" / "public" / "data" / "balanced_fix_baseline_metadata.json"
)

EXPECTED_YEARS = tuple(range(2035, 2101, 5))
CURRENT_LAW_EMPLOYEE_SS_RATE = 0.062
CURRENT_LAW_EMPLOYER_SS_RATE = 0.062
CURRENT_LAW_EMPLOYEE_HI_RATE = 0.0145
CURRENT_LAW_EMPLOYER_HI_RATE = 0.0145
MAX_ALLOWED_ABS_TOTAL_GAP_AFTER = 2_000_000


def _number(value: str) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _boolean(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def _read_metadata(recovered_dir: Path, year: int) -> dict[str, Any]:
    path = recovered_dir / "metadata" / f"{year}.metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing recovered metadata: {path}")
    return json.loads(path.read_text())


def _validate_rows(
    rows: list[dict[str, str]], recovered_dir: Path
) -> tuple[str, dict[str, Any]]:
    years = [int(_number(row["year"])) for row in rows]
    if tuple(years) != EXPECTED_YEARS:
        raise ValueError(f"Expected years {EXPECTED_YEARS}; found {tuple(years)}")

    run_prefixes: set[str] = set()
    first_metadata: dict[str, Any] | None = None
    for row in rows:
        year = int(_number(row["year"]))
        if not _boolean(row["full_reform_output_h5_saved"]):
            raise ValueError(f"{year}: full reform H5 was not saved")
        if not _boolean(row["object_store_upload_validated"]):
            raise ValueError(f"{year}: R2 upload validation is false")
        if abs(_number(row["total_gap_after"])) > MAX_ALLOWED_ABS_TOTAL_GAP_AFTER:
            raise ValueError(
                f"{year}: residual gap exceeds ${MAX_ALLOWED_ABS_TOTAL_GAP_AFTER:,}"
            )

        metadata = _read_metadata(recovered_dir, year)
        first_metadata = first_metadata or metadata
        run_prefixes.add(str(metadata["run_prefix"]))
        if metadata["schema"] != "crfb_balanced_fix_full_reform_h5_metadata/v1":
            raise ValueError(f"{year}: unexpected metadata schema")
        if metadata["reform_id"] != "balanced_fix":
            raise ValueError(f"{year}: unexpected reform id")
        if not metadata["full_reform_output_h5_saved"]:
            raise ValueError(f"{year}: metadata says H5 was not saved")
        if metadata["manual_weight_aggregation_used"]:
            raise ValueError(f"{year}: manual weight aggregation was used")
        if metadata["baseline_aggregate_metrics_computed_before_h5_save"]:
            raise ValueError(f"{year}: baseline aggregates were computed before H5 save")
        if (
            metadata.get("dataset_contract_environment", {}).get(
                "CRFB_SUPPORT_GATE_START_YEAR"
            )
            != "2101"
        ):
            raise ValueError(f"{year}: late-year support gate override is missing")
        if metadata.get("scenario_h5", {}).get("skipped_variable_count") != 0:
            raise ValueError(f"{year}: scenario H5 skipped variables")
        if metadata.get("scenario_h5", {}).get("tob_materialization", {}).get(
            "weighted_aggregation_used"
        ):
            raise ValueError(f"{year}: TOB materialization used weighted aggregation")

    if len(run_prefixes) != 1:
        raise ValueError(f"Expected one run prefix; found {sorted(run_prefixes)}")
    if first_metadata is None:
        raise ValueError("No rows found")
    return next(iter(run_prefixes)), first_metadata


def _dashboard_row(row: dict[str, str]) -> dict[str, Any]:
    year = int(_number(row["year"]))
    benefit_multiplier = _number(row["benefit_multiplier"])
    employee_ss_rate = _number(row["new_employee_ss_rate"])
    employer_ss_rate = _number(row["new_employer_ss_rate"])
    employee_hi_rate = _number(row["new_employee_hi_rate"])
    employer_hi_rate = _number(row["new_employer_hi_rate"])
    combined_ss_rate = employee_ss_rate + employer_ss_rate
    combined_hi_rate = employee_hi_rate + employer_hi_rate

    return {
        "year": year,
        "baseline_ss_gap_billions": _number(row["baseline_ss_gap"]) / 1e9,
        "baseline_hi_gap_billions": _number(row["baseline_hi_gap"]) / 1e9,
        "benefit_multiplier": benefit_multiplier,
        "benefit_cut_billions": _number(row["benefit_cut"]) / 1e9,
        "benefit_cut_pct": (1 - benefit_multiplier) * 100,
        "employee_ss_rate_pct": employee_ss_rate * 100,
        "employer_ss_rate_pct": employer_ss_rate * 100,
        "combined_ss_rate_pct": combined_ss_rate * 100,
        "employee_hi_rate_pct": employee_hi_rate * 100,
        "employer_hi_rate_pct": employer_hi_rate * 100,
        "combined_hi_rate_pct": combined_hi_rate * 100,
        "ss_rate_increase_pp": (combined_ss_rate - (
            CURRENT_LAW_EMPLOYEE_SS_RATE + CURRENT_LAW_EMPLOYER_SS_RATE
        )) * 100,
        "hi_rate_increase_pp": (combined_hi_rate - (
            CURRENT_LAW_EMPLOYEE_HI_RATE + CURRENT_LAW_EMPLOYER_HI_RATE
        )) * 100,
        "income_tax_impact_billions": _number(row["income_tax_impact"]) / 1e9,
        "tob_oasdi_impact_billions": _number(row["tob_oasdi_impact"]) / 1e9,
        "tob_hi_impact_billions": _number(row["tob_hi_impact"]) / 1e9,
        "rate_increase_ss_revenue_billions": _number(
            row["rate_increase_ss_revenue"]
        )
        / 1e9,
        "rate_increase_hi_revenue_billions": _number(
            row["rate_increase_hi_revenue"]
        )
        / 1e9,
        "total_rate_increase_revenue_billions": _number(
            row["total_rate_increase_revenue"]
        )
        / 1e9,
        "ss_gap_after_millions": _number(row["ss_gap_after"]) / 1e6,
        "hi_gap_after_millions": _number(row["hi_gap_after"]) / 1e6,
        "total_gap_after_millions": _number(row["total_gap_after"]) / 1e6,
        "scenario_h5_uri": row["scenario_h5_uri"],
        "metadata_uri": row["metadata_uri"],
        "completion_uri": row["completion_uri"],
        "output_h5_sha256": row["output_h5_sha256"],
        "source": "exact_full_h5_balanced_fix_option13_20260522",
    }


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def publish(
    *,
    source_path: Path,
    recovered_dir: Path,
    output_path: Path,
    metadata_output_path: Path,
) -> dict[str, Any]:
    rows = sorted(_read_csv(source_path), key=lambda row: int(_number(row["year"])))
    run_prefix, first_metadata = _validate_rows(rows, recovered_dir)
    dashboard_rows = [_dashboard_row(row) for row in rows]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(dashboard_rows[0].keys()))
        writer.writeheader()
        writer.writerows(dashboard_rows)

    packages = first_metadata.get("runtime_provenance", {}).get("packages", {})
    metadata = {
        "schema": "crfb_balanced_fix_dashboard_data/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": _repo_path(source_path),
        "recovered_dir": _repo_path(recovered_dir),
        "output_path": _repo_path(output_path),
        "run_prefix": run_prefix,
        "reform_id": "balanced_fix",
        "source_result_count": len(rows),
        "years": list(EXPECTED_YEARS),
        "full_reform_h5_saved": True,
        "object_store_upload_validated": True,
        "raw_h5_persistence": "scenario_h5_uri and metadata_uri point to R2 objects for every row",
        "manual_weight_aggregation_used": False,
        "baseline_aggregate_metrics_computed_before_h5_save": False,
        "unit_conversion": "source dollars divided by 1e9 for billions and 1e6 for residual-gap millions; source rates multiplied by 100 for percentages",
        "interpolation_used": False,
        "support_gate_override": "CRFB_SUPPORT_GATE_START_YEAR=2101",
        "max_abs_total_gap_after_millions": max(
            abs(_number(row["total_gap_after"])) / 1e6 for row in rows
        ),
        "runtime_packages": {
            "policyengine": packages.get("policyengine"),
            "policyengine-us": packages.get("policyengine-us"),
            "policyengine-core": packages.get("policyengine-core"),
            "policyengine-us-data": packages.get("policyengine-us-data"),
            "microdf-python": packages.get("microdf-python"),
        },
    }
    metadata_output_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--recovered-dir", type=Path, default=DEFAULT_RECOVERED_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT
    )
    args = parser.parse_args()
    metadata = publish(
        source_path=args.source,
        recovered_dir=args.recovered_dir,
        output_path=args.output,
        metadata_output_path=args.metadata_output,
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
