from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from modal_run_protocol import (
    BASELINE_SCENARIO,
    summarize_run_directory,
    year_artifact_paths,
    scenario_artifact_paths,
    within_run_root,
)
from year_runner import (
    BATCH_EMPLOYER_NET_REFORMS,
    BaselineResult,
    ScenarioHouseholdMetrics,
    aggregate_scenario_household_metrics,
    build_reform_result_from_aggregates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate a recovered Modal scenario run into reform impact tables."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Local recovered run directory containing manifest.json and scenario files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Combined CSV path for all aggregated reform results.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow aggregation even if some scenario cells are not completed.",
    )
    return parser.parse_args()


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


def load_weights(path: Path) -> tuple[np.ndarray, np.ndarray]:
    payload = np.load(path)
    return (
        np.asarray(payload["household_ids"]),
        np.asarray(payload["household_weights"], dtype=float),
    )


def ensure_aggregatable_run(
    run_dir: Path,
    manifest: dict,
    *,
    allow_incomplete: bool,
) -> None:
    if not manifest.get("include_baseline", True):
        raise ValueError(
            "This run was submitted without baseline cells and cannot be aggregated "
            "into reform impacts."
        )

    summary = summarize_run_directory(run_dir, manifest)
    if summary["failed_cells"] > 0:
        raise ValueError(
            f"Run contains failed cells and cannot be aggregated: {summary['failed']}"
        )
    if not allow_incomplete and summary["pending_cells"] > 0:
        raise ValueError(
            "Run is incomplete and cannot be aggregated yet. "
            f"Pending cells: {summary['pending']}"
        )


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    ensure_aggregatable_run(
        run_dir,
        manifest,
        allow_incomplete=args.allow_incomplete,
    )

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    years = [int(year) for year in manifest["years"]]
    for year in years:
        year_paths = year_artifact_paths(manifest["run_id"], year)
        weights_path = run_dir / within_run_root(
            manifest["run_id"], year_paths["weights"]
        )
        if not weights_path.exists():
            raise FileNotFoundError(
                f"Recovered run is missing weight bundle for year {year}: {weights_path}"
            )
        weight_household_ids, household_weights = load_weights(weights_path)

        baseline_paths = scenario_artifact_paths(
            manifest["run_id"],
            year,
            BASELINE_SCENARIO,
        )
        baseline_success_path = run_dir / within_run_root(
            manifest["run_id"], baseline_paths["success"]
        )
        if not baseline_success_path.exists():
            raise FileNotFoundError(
                f"Recovered run is missing completed baseline for year {year}: "
                f"{baseline_success_path}"
            )
        baseline_metrics = load_metrics(
            run_dir / within_run_root(manifest["run_id"], baseline_paths["metrics"])
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

        for reform_id in manifest["reforms"]:
            reform_paths = scenario_artifact_paths(
                manifest["run_id"],
                year,
                reform_id,
            )
            success_path = run_dir / within_run_root(
                manifest["run_id"], reform_paths["success"]
            )
            if not success_path.exists():
                if args.allow_incomplete:
                    continue
                raise FileNotFoundError(
                    f"Recovered run is missing completed reform cell for "
                    f"year {year}, reform {reform_id}: {success_path}"
                )
            reform_metrics = load_metrics(
                run_dir / within_run_root(manifest["run_id"], reform_paths["metrics"])
            )
            reform_aggregate = aggregate_scenario_household_metrics(
                reform_metrics,
                weight_household_ids=weight_household_ids,
                household_weights=household_weights,
            )
            row = build_reform_result_from_aggregates(
                reform_id=reform_id,
                year=year,
                baseline=baseline,
                reform_totals=reform_aggregate,
                employer_net_reforms=BATCH_EMPLOYER_NET_REFORMS,
                default_net_impact_mode="direct",
                scoring_type=manifest["scoring"],
            )
            row["run_id"] = manifest["run_id"]
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Wrote {output_path}")
    print(df.to_json(orient="records", indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
