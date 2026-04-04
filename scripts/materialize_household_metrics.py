from __future__ import annotations
# ruff: noqa: E402

import argparse
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from runtime_config import resolve_policyengine_us_path

policyengine_us_path = resolve_policyengine_us_path()
if str(policyengine_us_path) not in sys.path:
    sys.path.insert(0, str(policyengine_us_path))

from year_runner import (
    compute_scenario_household_metrics,
    build_reform,
    get_reform_lookups,
)


DEFAULT_TAX_ASSUMPTION_FACTORY = "create_wage_indexed_core_thresholds_reform"


def _candidate_tax_assumption_modules() -> list[Path]:
    return [
        Path.home()
        / ".codex-worktrees"
        / "us-data-calibration-contract"
        / "policyengine_us_data"
        / "datasets"
        / "cps"
        / "long_term"
        / "tax_assumptions.py",
        REPO_ROOT.parent
        / "policyengine-us-data"
        / "policyengine_us_data"
        / "datasets"
        / "cps"
        / "long_term"
        / "tax_assumptions.py",
    ]


def resolve_tax_assumption_module(module_path: str | None) -> Path:
    if module_path:
        path = Path(module_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    for candidate in _candidate_tax_assumption_modules():
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "Could not resolve a tax assumption module. Pass --tax-assumption-module."
    )


def load_tax_assumption_reform(
    module_path: Path, factory_name: str, start_year: int, end_year: int
):
    spec = importlib.util.spec_from_file_location("tax_assumptions", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load tax assumption module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, factory_name)
    return factory(start_year=start_year, end_year=end_year)


def scenario_path(output_dir: Path, label: str, year: int, scenario_name: str) -> Path:
    safe_label = label.replace("/", "_")
    return output_dir / f"{safe_label}__{year}__{scenario_name}.npz"


def write_metrics(
    output_path: Path,
    *,
    metrics,
    metadata: dict[str, object],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        household_ids=metrics.household_ids,
        income_tax=metrics.income_tax,
        tob_medicare_hi=metrics.tob_medicare_hi,
        tob_oasdi=metrics.tob_oasdi,
        employer_ss_tax_revenue=metrics.employer_ss_tax_revenue,
        employer_medicare_tax_revenue=metrics.employer_medicare_tax_revenue,
    )
    output_path.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_metrics_metadata(
    *,
    year: int,
    dataset_path: Path,
    dataset_label: str,
    scenario_name: str,
    scoring_type: str,
    tax_assumption_module: Path,
    tax_assumption_factory: str,
    reform_id: str | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "year": year,
        "dataset_path": str(dataset_path),
        "dataset_label": dataset_label,
        "scenario": scenario_name,
        "scoring_type": scoring_type,
        "tax_assumption_module": str(tax_assumption_module),
        "tax_assumption_factory": tax_assumption_factory,
    }
    if reform_id is not None:
        metadata["reform_id"] = reform_id
    return metadata


def materialize_and_write(
    *,
    year: int,
    dataset_path: Path,
    label: str,
    scenario_name: str,
    reform,
    output_dir: Path,
    scoring_type: str,
    tax_assumption_module: Path,
    tax_assumption_factory: str,
    reform_id: str | None = None,
) -> Path:
    metrics = compute_scenario_household_metrics(
        year=year,
        dataset_name=dataset_path,
        reform=reform,
    )
    output_path = scenario_path(output_dir, label, year, scenario_name)
    write_metrics(
        output_path,
        metrics=metrics,
        metadata=build_metrics_metadata(
            year=year,
            dataset_path=dataset_path,
            dataset_label=label,
            scenario_name=scenario_name,
            scoring_type=scoring_type,
            tax_assumption_module=tax_assumption_module,
            tax_assumption_factory=tax_assumption_factory,
            reform_id=reform_id,
        ),
    )
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize household-level scenario outputs that can be aggregated "
            "later with calibrated weights."
        )
    )
    parser.add_argument("--year", type=int, required=True, help="Simulation year.")
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to the support dataset to simulate on.",
    )
    parser.add_argument(
        "--label",
        required=True,
        help="Short dataset label used in output file names.",
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
    dataset_path = Path(args.dataset).expanduser().resolve()
    tax_assumption_module = resolve_tax_assumption_module(args.tax_assumption_module)
    baseline_reform = load_tax_assumption_reform(
        tax_assumption_module,
        args.tax_assumption_factory,
        args.tax_assumption_start_year,
        args.tax_assumption_end_year,
    )
    reform_functions, dynamic_functions = get_reform_lookups()

    if args.include_baseline:
        output_path = materialize_and_write(
            year=args.year,
            dataset_path=dataset_path,
            label=args.label,
            scenario_name="baseline",
            reform=baseline_reform,
            output_dir=output_dir,
            scoring_type=args.scoring_type,
            tax_assumption_module=tax_assumption_module,
            tax_assumption_factory=args.tax_assumption_factory,
        )
        print(f"Wrote {output_path}")

    for reform_id in args.reform:
        reform = build_reform(
            reform_id,
            args.scoring_type,
            reform_functions,
            dynamic_functions,
        )
        combined_reform = (baseline_reform, reform)
        output_path = materialize_and_write(
            year=args.year,
            dataset_path=dataset_path,
            label=args.label,
            scenario_name=reform_id,
            reform=combined_reform,
            output_dir=output_dir,
            scoring_type=args.scoring_type,
            tax_assumption_module=tax_assumption_module,
            tax_assumption_factory=args.tax_assumption_factory,
            reform_id=reform_id,
        )
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
