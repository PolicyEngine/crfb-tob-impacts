#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from modal_run_recover import download_volume_prefix
from year_runner import (
    BaselineResult,
    MODAL_EMPLOYER_NET_REFORMS,
    build_reform_result_from_aggregates,
    scenario_aggregate_from_dict,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recover Modal scenario artifacts and derive the reform delta CSV "
            "from saved baseline/reform aggregate JSON files."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help=(
            "Submission manifest produced by "
            "modal_batch/compute.py::submit_scenario_artifacts."
        ),
    )
    parser.add_argument(
        "--output-prefix",
        help="Volume prefix under crfb-results. Optional when --manifest is provided.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Local directory for recovered artifacts. Optional when manifest has output_dir.",
    )
    parser.add_argument(
        "--combined-output",
        type=Path,
        help="Combined delta CSV path. Optional when manifest has output.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Combine artifacts already present in --output-dir without Modal download.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_dir(output_dir: Path, year: int, scenario_id: str) -> Path:
    return output_dir / "scenarios" / f"year={year}" / f"scenario={scenario_id}"


def scenario_aggregate(output_dir: Path, year: int, scenario_id: str):
    path = scenario_dir(output_dir, year, scenario_id) / "aggregates.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing scenario aggregate artifact: {path}")
    return scenario_aggregate_from_dict(load_json(path))


def scenario_metadata(output_dir: Path, year: int, scenario_id: str) -> dict:
    path = scenario_dir(output_dir, year, scenario_id) / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing scenario metadata artifact: {path}")
    return load_json(path)


def validate_scenario_artifact(
    *,
    output_dir: Path,
    year: int,
    scenario_id: str,
    scoring: str,
    volume_prefix: str,
) -> None:
    artifact_dir = scenario_dir(output_dir, year, scenario_id)
    required_files = [
        "metrics.npz",
        "weights.npz",
        "aggregates.json",
        "metadata.json",
    ]
    missing = [name for name in required_files if not (artifact_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"{artifact_dir} is missing expected scenario artifacts: "
            + ", ".join(missing)
        )

    metadata = scenario_metadata(output_dir, year, scenario_id)
    expected = {
        "year": int(year),
        "scenario_id": scenario_id,
        "scoring_type": scoring,
        "volume_prefix": volume_prefix.strip("/"),
    }
    mismatches = [
        f"{key}={metadata.get(key)!r}, expected {value!r}"
        for key, value in expected.items()
        if metadata.get(key) != value
    ]
    if mismatches:
        raise ValueError(
            f"{artifact_dir} metadata does not match the submitted run: "
            + "; ".join(mismatches)
        )


def validate_expected_scenario_artifacts(
    *,
    output_dir: Path,
    scenarios: list[str],
    years: list[int],
    scoring: str,
    volume_prefix: str,
) -> None:
    failures = []
    for year in years:
        for scenario_id in scenarios:
            try:
                validate_scenario_artifact(
                    output_dir=output_dir,
                    year=year,
                    scenario_id=scenario_id,
                    scoring=scoring,
                    volume_prefix=volume_prefix,
                )
            except (FileNotFoundError, ValueError) as error:
                failures.append(str(error))

    if failures:
        raise RuntimeError(
            "Recovered scenario artifact validation failed:\n"
            + "\n".join(f"  - {failure}" for failure in failures)
        )


def combine_scenario_artifacts(
    *,
    output_dir: Path,
    combined_output: Path,
    reforms: list[str],
    years: list[int],
    scoring: str,
) -> None:
    rows = []
    for year in years:
        baseline_aggregate = scenario_aggregate(output_dir, year, "baseline")
        baseline_metadata = scenario_metadata(output_dir, year, "baseline")
        tax_assumption = baseline_metadata.get("tax_assumption", {})
        baseline = BaselineResult(
            revenue=baseline_aggregate.revenue,
            tob_medicare_hi=baseline_aggregate.tob_medicare_hi,
            tob_oasdi=baseline_aggregate.tob_oasdi,
            tob_total=baseline_aggregate.tob_total,
            social_security=baseline_aggregate.social_security,
            taxable_payroll=baseline_aggregate.taxable_payroll,
            tax_assumption_name=tax_assumption.get("name"),
            tax_assumption_active=bool(tax_assumption.get("active", False)),
        )

        for reform_id in reforms:
            reform_aggregate = scenario_aggregate(output_dir, year, reform_id)
            row = build_reform_result_from_aggregates(
                reform_id=reform_id,
                year=year,
                baseline=baseline,
                reform_totals=reform_aggregate,
                employer_net_reforms=MODAL_EMPLOYER_NET_REFORMS,
                default_net_impact_mode="direct",
                scoring_type=scoring,
            )
            row.update(
                {
                    "baseline_artifact_dir": str(
                        scenario_dir(output_dir, year, "baseline")
                    ),
                    "reform_artifact_dir": str(
                        scenario_dir(output_dir, year, reform_id)
                    ),
                }
            )
            rows.append(row)

    if not rows:
        raise ValueError("No scenario artifact rows were combined.")

    frame = pd.DataFrame(rows).sort_values(["reform_name", "year"])
    combined_output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(combined_output, index=False)
    print(f"Combined {len(rows)} reform-year rows into {combined_output}")


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest) if args.manifest else {}

    output_prefix = args.output_prefix or manifest.get("volume_prefix")
    output_dir = args.output_dir or Path(manifest.get("output_dir", ""))
    combined_output = args.combined_output or Path(manifest.get("output", ""))
    reforms = manifest.get("reforms", [])
    scenarios = manifest.get("scenarios", ["baseline", *reforms])
    years = [int(year) for year in manifest.get("years", [])]
    scoring = manifest.get("scoring", "static")

    if not str(output_dir):
        raise ValueError("Provide --output-dir or --manifest with output_dir.")
    if not str(combined_output):
        raise ValueError("Provide --combined-output or --manifest with output.")
    if not reforms:
        raise ValueError("Manifest must include reforms.")
    if not years:
        raise ValueError("Manifest must include years.")

    output_dir = output_dir.resolve()
    combined_output = combined_output.resolve()

    if not args.skip_download:
        if not output_prefix:
            raise ValueError(
                "Provide --output-prefix or --manifest with volume_prefix."
            )
        recovered = download_volume_prefix(output_prefix, output_dir)
        print(f"Recovery marker: {recovered}")

    validate_expected_scenario_artifacts(
        output_dir=output_dir,
        scenarios=scenarios,
        years=years,
        scoring=scoring,
        volume_prefix=output_prefix or "",
    )
    combine_scenario_artifacts(
        output_dir=output_dir,
        combined_output=combined_output,
        reforms=reforms,
        years=years,
        scoring=scoring,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
