from __future__ import annotations
# ruff: noqa: E402

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from materialize_household_metrics import (
    build_reform,
    build_metrics_metadata,
    compute_scenario_household_metrics,
    get_reform_lookups,
    load_tax_assumption_reform,
    resolve_tax_assumption_module,
    scenario_path,
    write_metrics,
)


DEFAULT_TAX_ASSUMPTION_FACTORY = "create_wage_indexed_core_thresholds_reform"


def parse_dataset_spec(spec: str) -> tuple[str, Path, int]:
    if "=" not in spec:
        raise ValueError(f"Invalid dataset spec '{spec}'. Expected label=/path/to/year.h5")
    label, raw_path = spec.split("=", 1)
    path = Path(raw_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        year = int(path.stem)
    except ValueError as exc:
        raise ValueError(
            f"Could not infer year from dataset filename '{path.name}'. Use files named like 2075.h5."
        ) from exc
    return label, path, year


def materialize_task(
    *,
    label: str,
    dataset_path: str,
    year: int,
    scenario_name: str,
    reform_id: str | None,
    scoring_type: str,
    output_dir: str,
    tax_assumption_module: str,
    tax_assumption_factory: str,
    tax_assumption_start_year: int,
    tax_assumption_end_year: int,
) -> str:
    dataset = Path(dataset_path)
    output_root = Path(output_dir)
    baseline_reform = load_tax_assumption_reform(
        Path(tax_assumption_module),
        tax_assumption_factory,
        tax_assumption_start_year,
        tax_assumption_end_year,
    )

    reform = baseline_reform
    metadata = build_metrics_metadata(
        year=year,
        dataset_path=dataset,
        dataset_label=label,
        scenario_name=scenario_name,
        scoring_type=scoring_type,
        tax_assumption_module=Path(tax_assumption_module),
        tax_assumption_factory=tax_assumption_factory,
        reform_id=reform_id,
    )

    if reform_id is not None:
        reform_functions, dynamic_functions = get_reform_lookups()
        built_reform = build_reform(
            reform_id,
            scoring_type,
            reform_functions,
            dynamic_functions,
        )
        reform = (baseline_reform, built_reform)

    metrics = compute_scenario_household_metrics(
        year=year,
        dataset_name=dataset,
        reform=reform,
    )
    output_path = scenario_path(output_root, label, year, scenario_name)
    write_metrics(output_path, metrics=metrics, metadata=metadata)
    return str(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize household-level scenario outputs in parallel across a grid "
            "of datasets and reforms."
        )
    )
    parser.add_argument(
        "--dataset",
        action="append",
        required=True,
        help="Dataset spec in the form label=/absolute/path/to/<year>.h5.",
    )
    parser.add_argument(
        "--reform",
        action="append",
        default=[],
        help="Reform ID to materialize. Repeatable.",
    )
    parser.add_argument(
        "--include-baseline",
        action="store_true",
        help="Also materialize the baseline scenario.",
    )
    parser.add_argument(
        "--scoring-type",
        default="static",
        choices=["static", "dynamic"],
        help="CRFB scoring type to use when building reforms.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Maximum number of worker processes.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip scenarios whose output .npz already exists.",
    )
    parser.add_argument(
        "--tax-assumption-module",
        help="Path to the long-run tax assumption module.",
    )
    parser.add_argument(
        "--tax-assumption-factory",
        default=DEFAULT_TAX_ASSUMPTION_FACTORY,
        help="Factory function name inside --tax-assumption-module.",
    )
    parser.add_argument(
        "--tax-assumption-start-year",
        type=int,
        default=2035,
        help="Start year for the baseline tax assumption reform.",
    )
    parser.add_argument(
        "--tax-assumption-end-year",
        type=int,
        default=2100,
        help="End year for the baseline tax assumption reform.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where scenario .npz files will be written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    tax_assumption_module = resolve_tax_assumption_module(args.tax_assumption_module)

    tasks: list[dict[str, object]] = []
    for dataset_spec in args.dataset:
        label, dataset_path, year = parse_dataset_spec(dataset_spec)
        if args.include_baseline:
            baseline_path = scenario_path(output_dir, label, year, "baseline")
            if not (args.skip_existing and baseline_path.exists()):
                tasks.append(
                    {
                        "label": label,
                        "dataset_path": str(dataset_path),
                        "year": year,
                        "scenario_name": "baseline",
                        "reform_id": None,
                    }
                )
        for reform_id in args.reform:
            reform_path = scenario_path(output_dir, label, year, reform_id)
            if args.skip_existing and reform_path.exists():
                continue
            tasks.append(
                {
                    "label": label,
                    "dataset_path": str(dataset_path),
                    "year": year,
                    "scenario_name": reform_id,
                    "reform_id": reform_id,
                }
            )

    if not tasks:
        print("No materialization tasks to run.")
        return

    futures = []
    with ProcessPoolExecutor(max_workers=max(args.jobs, 1)) as executor:
        for task in tasks:
            futures.append(
                executor.submit(
                    materialize_task,
                    **task,
                    scoring_type=args.scoring_type,
                    output_dir=str(output_dir),
                    tax_assumption_module=str(tax_assumption_module),
                    tax_assumption_factory=args.tax_assumption_factory,
                    tax_assumption_start_year=args.tax_assumption_start_year,
                    tax_assumption_end_year=args.tax_assumption_end_year,
                )
            )

        for future in as_completed(futures):
            output_path = future.result()
            print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
