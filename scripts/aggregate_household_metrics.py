from __future__ import annotations
# ruff: noqa: E402

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from runtime_config import resolve_policyengine_us_path, validate_dataset_contract

policyengine_us_path = resolve_policyengine_us_path()
if str(policyengine_us_path) not in sys.path:
    sys.path.insert(0, str(policyengine_us_path))

from year_runner import (
    BATCH_EMPLOYER_NET_REFORMS,
    BaselineResult,
    ScenarioHouseholdMetrics,
    aggregate_scenario_household_metrics,
    build_reform_result_from_aggregates,
    load_household_weights,
)


def scenario_path(input_dir: Path, label: str, year: int, scenario_name: str) -> Path:
    safe_label = label.replace("/", "_")
    return input_dir / f"{safe_label}__{year}__{scenario_name}.npz"


def load_metrics(path: Path) -> ScenarioHouseholdMetrics:
    payload = np.load(path)
    return ScenarioHouseholdMetrics(
        household_ids=np.asarray(payload["household_ids"]),
        income_tax=np.asarray(payload["income_tax"], dtype=float),
        tob_medicare_hi=np.asarray(payload["tob_medicare_hi"], dtype=float),
        tob_oasdi=np.asarray(payload["tob_oasdi"], dtype=float),
        employer_ss_tax_revenue=np.asarray(
            payload["employer_ss_tax_revenue"], dtype=float
        ),
        employer_medicare_tax_revenue=np.asarray(
            payload["employer_medicare_tax_revenue"], dtype=float
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate household-level scenario outputs with calibrated weights."
        )
    )
    parser.add_argument("--year", type=int, required=True, help="Simulation year.")
    parser.add_argument(
        "--label",
        required=True,
        help="Dataset label used in scenario file names.",
    )
    parser.add_argument(
        "--weights-dataset",
        required=True,
        help="Path to the calibrated H5 whose household weights should be applied.",
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing scenario .npz files from materialize_household_metrics.py.",
    )
    parser.add_argument(
        "--reform",
        action="append",
        required=True,
        help="Reform ID to aggregate. Repeatable.",
    )
    parser.add_argument(
        "--output",
        help="Optional output CSV path.",
    )
    parser.add_argument(
        "--required-profile",
        default="ss-payroll-tob",
        help="Expected calibration profile name recorded in the weights dataset metadata.",
    )
    parser.add_argument(
        "--required-target-source",
        default="oact_2025_08_05_provisional",
        help="Expected target source name recorded in the weights dataset metadata.",
    )
    parser.add_argument(
        "--required-tax-assumption",
        default="trustees-core-thresholds-v1",
        help="Expected tax assumption name recorded in the weights dataset metadata.",
    )
    parser.add_argument(
        "--minimum-calibration-quality",
        default="aggregate",
        choices=["aggregate", "approximate", "exact"],
        help="Minimum calibration quality required in the weights dataset metadata.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    weights_dataset = Path(args.weights_dataset).expanduser().resolve()
    input_dir = Path(args.input_dir).expanduser().resolve()

    validate_dataset_contract(
        weights_dataset,
        required_profile=args.required_profile,
        minimum_calibration_quality=args.minimum_calibration_quality,
        required_target_source=args.required_target_source,
        required_tax_assumption=args.required_tax_assumption,
        reject_aggregate=False,
        allow_unvalidated=False,
    )

    weight_household_ids, household_weights = load_household_weights(weights_dataset)
    baseline_metrics = load_metrics(
        scenario_path(input_dir, args.label, args.year, "baseline")
    )
    baseline_aggregate = aggregate_scenario_household_metrics(
        baseline_metrics,
        weight_household_ids=weight_household_ids,
        household_weights=household_weights,
    )
    baseline = BaselineResult(
        revenue=baseline_aggregate.revenue,
        tob_medicare_hi=baseline_aggregate.tob_medicare_hi,
        tob_oasdi=baseline_aggregate.tob_oasdi,
        tob_total=baseline_aggregate.tob_total,
    )

    rows: list[dict[str, float | int | str]] = []
    for reform_id in args.reform:
        reform_metrics = load_metrics(
            scenario_path(input_dir, args.label, args.year, reform_id)
        )
        reform_aggregate = aggregate_scenario_household_metrics(
            reform_metrics,
            weight_household_ids=weight_household_ids,
            household_weights=household_weights,
        )
        row = build_reform_result_from_aggregates(
            reform_id=reform_id,
            year=args.year,
            baseline=baseline,
            reform_totals=reform_aggregate,
            employer_net_reforms=BATCH_EMPLOYER_NET_REFORMS,
            default_net_impact_mode="direct",
        )
        row["dataset_label"] = args.label
        row["weights_dataset"] = str(weights_dataset)
        rows.append(row)

    df = pd.DataFrame(rows)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.10f")
        print(f"Wrote {output_path}")

    print(df.to_json(orient="records", indent=2))


if __name__ == "__main__":
    main()
