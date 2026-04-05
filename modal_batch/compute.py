"""
Modal-based compute functions for Social Security reform analysis.

This provides a parallel alternative to the GCP Batch infrastructure,
reusing the same reform definitions from src/reforms.py.

Usage:
    # Sniff test a few years
    modal run compute.py::sniff_test --reforms option9,option10,option11

    # Run all years for new options
    modal run compute.py::run_reforms --reforms option9,option10,option11 --scoring dynamic
"""
# ruff: noqa: E402

from __future__ import annotations

from datetime import datetime
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

import modal
import pandas as pd


LOCAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_PROJECT_ROOT = Path("/app")

path_candidates = [LOCAL_PROJECT_ROOT / "src", CONTAINER_PROJECT_ROOT / "src"]
for path in reversed(path_candidates):
    if path.exists():
        sys.path.insert(0, str(path))

from modal_run_protocol import (
    run_paths,
    year_artifact_paths,
    scenario_artifact_paths,
)
from modal_cli import modal_cli_prefix
from runtime_config import resolve_policyengine_us_path, resolve_projected_datasets_path
from tax_assumption_loader import resolve_tax_assumption_module


app = modal.App("crfb-ss-analysis")
results_volume = modal.Volume.from_name("crfb-results", create_if_missing=True)

if (CONTAINER_PROJECT_ROOT / "policyengine-us").exists():
    POLICYENGINE_US_PATH = CONTAINER_PROJECT_ROOT / "policyengine-us"
else:
    POLICYENGINE_US_PATH = resolve_policyengine_us_path()

if (CONTAINER_PROJECT_ROOT / "projected_datasets").exists():
    PROJECTED_DATASETS_PATH = CONTAINER_PROJECT_ROOT / "projected_datasets"
else:
    PROJECTED_DATASETS_PATH = resolve_projected_datasets_path()

TAX_ASSUMPTION_CONTAINER_DIR = CONTAINER_PROJECT_ROOT / "tax_assumptions"
if TAX_ASSUMPTION_CONTAINER_DIR.exists():
    TAX_ASSUMPTION_LOCAL_PATH = TAX_ASSUMPTION_CONTAINER_DIR / "tax_assumptions.py"
else:
    TAX_ASSUMPTION_LOCAL_PATH = resolve_tax_assumption_module(
        os.environ.get("CRFB_TAX_ASSUMPTION_MODULE")
    )
TAX_ASSUMPTION_CONTAINER_PATH = TAX_ASSUMPTION_CONTAINER_DIR / TAX_ASSUMPTION_LOCAL_PATH.name

POLICYENGINE_US_IGNORE = [
    ".claude",
    ".claude/**",
    ".git",
    ".git/**",
    ".github",
    ".github/**",
    ".pytest_cache",
    ".pytest_cache/**",
    ".venv",
    ".venv/**",
    ".vscode",
    ".vscode/**",
    "docs",
    "docs/**",
    "changelog.d",
    "changelog.d/**",
    "policyengine_us/tests",
    "policyengine_us/tests/**",
    "**/__pycache__",
    "**/*.pyc",
]

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "pandas>=2.0.0",
        "numpy>=1.24.0",
    )
    .add_local_dir(
        POLICYENGINE_US_PATH,
        "/app/policyengine-us",
        copy=True,
        ignore=POLICYENGINE_US_IGNORE,
    )
    .run_commands("pip install -e /app/policyengine-us")
    .add_local_dir(LOCAL_PROJECT_ROOT / "src", "/app/src", copy=True)
    .add_local_dir(PROJECTED_DATASETS_PATH, "/app/projected_datasets", copy=True)
    .add_local_dir(
        TAX_ASSUMPTION_LOCAL_PATH.parent,
        str(TAX_ASSUMPTION_CONTAINER_DIR),
        copy=True,
    )
)


def _stem_with_scoring(stem: str, scoring: str) -> str:
    suffix = f"_{scoring}"
    return stem if stem.endswith(suffix) else f"{stem}{suffix}"


def _parse_years(years: str) -> list[int]:
    if "-" in years:
        start, end = years.split("-")
        return list(range(int(start), int(end) + 1))
    return [int(year.strip()) for year in years.split(",") if year.strip()]


def _recursive_reform_list(output_dir: Path) -> list[str]:
    return sorted(
        path.name
        for path in output_dir.iterdir()
        if path.is_dir() and path.name.startswith("option")
    )


def _write_error_artifact(save_path: str, message: str) -> None:
    error_path = Path("/results") / f"{save_path}.error.txt"
    error_path.parent.mkdir(parents=True, exist_ok=True)
    error_path.write_text(message, encoding="utf-8")
    results_volume.commit()
    print(f"SAVED ERROR TO VOLUME: {error_path}")


def _absolute_volume_path(path: Path) -> Path:
    return Path("/results") / path


def _write_json_volume(path: Path, payload: dict) -> None:
    volume_path = _absolute_volume_path(path)
    volume_path.parent.mkdir(parents=True, exist_ok=True)
    volume_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _tax_assumption_runtime_path() -> Path:
    if TAX_ASSUMPTION_CONTAINER_PATH.exists():
        return TAX_ASSUMPTION_CONTAINER_PATH
    return TAX_ASSUMPTION_LOCAL_PATH


def _load_remote_run_manifest(run_id: str) -> dict:
    manifest_path = _absolute_volume_path(run_paths(run_id).manifest)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Remote manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _scenario_metadata(
    *,
    spec: dict,
    cell: dict,
    dataset_name: str,
) -> dict:
    year = int(cell["year"])
    reform_id = cell.get("reform_id")
    return {
        "run_id": spec["run_id"],
        "year": year,
        "scenario_name": str(cell["scenario_name"]),
        "reform_id": reform_id,
        "scoring": spec["scoring"],
        "dataset": spec["datasets"][str(year)],
        "dataset_name": dataset_name,
        "tax_assumption": spec["tax_assumption"],
        "provenance": spec["provenance"],
    }


def _write_metrics_bundle(
    *,
    path_map: dict[str, Path],
    metrics,
    metadata: dict,
) -> None:
    import numpy as np

    metrics_path = _absolute_volume_path(path_map["metrics"])
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        metrics_path,
        household_ids=metrics.household_ids,
        income_tax=metrics.income_tax,
        tob_medicare_hi=metrics.tob_medicare_hi,
        tob_oasdi=metrics.tob_oasdi,
        employer_ss_tax_revenue=metrics.employer_ss_tax_revenue,
        employer_medicare_tax_revenue=metrics.employer_medicare_tax_revenue,
    )
    _write_json_volume(path_map["metadata"], metadata)


def _ensure_year_weight_bundle(
    *,
    spec: dict,
    year: int,
    dataset_name,
) -> None:
    import numpy as np

    sys.path.insert(0, "/app/src")

    from year_runner import load_household_weights

    path_map = year_artifact_paths(spec["run_id"], year)
    weights_path = _absolute_volume_path(path_map["weights"])
    if weights_path.exists():
        return

    weight_household_ids, household_weights = load_household_weights(dataset_name)
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        weights_path,
        household_ids=weight_household_ids,
        household_weights=household_weights,
    )
    _write_json_volume(
        path_map["metadata"],
        {
            "run_id": spec["run_id"],
            "year": year,
            "dataset_name": str(dataset_name),
            "dataset": spec["datasets"][str(year)],
        },
    )
    results_volume.commit()


def _materialize_scenario_impl(spec: dict, cell: dict) -> dict:
    import gc
    import time
    import warnings

    warnings.filterwarnings("ignore")
    os.environ.setdefault("CRFB_DATASET_TEMPLATE", "/app/projected_datasets/{year}.h5")

    sys.path.insert(0, "/app/src")

    from runtime_config import dataset_path
    from tax_assumption_loader import load_tax_assumption_reform
    from year_runner import (
        MODAL_UNSUPPORTED_REFORMS,
        build_reform,
        compute_scenario_household_metrics,
        get_reform_lookups,
    )

    year = int(cell["year"])
    scenario = str(cell["scenario_name"])
    reform_id = cell.get("reform_id")
    path_map = scenario_artifact_paths(spec["run_id"], year, scenario)
    success_path = _absolute_volume_path(path_map["success"])
    if success_path.exists():
        print(
            f"SKIP COMPLETED SCENARIO: run={spec['run_id']} year={year} "
            f"scenario={scenario}"
        )
        return {
            "run_id": spec["run_id"],
            "year": year,
            "scenario_name": scenario,
            "status": "already_completed",
        }

    started_at = datetime.utcnow().isoformat() + "Z"

    _write_json_volume(
        path_map["started"],
        {
            "run_id": spec["run_id"],
            "year": year,
            "scenario_name": scenario,
            "reform_id": reform_id,
            "started_at": started_at,
        },
    )
    results_volume.commit()

    dataset_name = dataset_path(year)
    start_time = time.time()

    try:
        _ensure_year_weight_bundle(
            spec=spec,
            year=year,
            dataset_name=dataset_name,
        )

        baseline_reform = load_tax_assumption_reform(
            _tax_assumption_runtime_path(),
            spec["tax_assumption"]["factory"],
            int(spec["tax_assumption"]["start_year"]),
            int(spec["tax_assumption"]["end_year"]),
        )

        reform = baseline_reform
        if reform_id is not None:
            reform_functions, dynamic_functions = get_reform_lookups(
                MODAL_UNSUPPORTED_REFORMS
            )
            reform = (
                baseline_reform,
                build_reform(
                    reform_id,
                    spec["scoring"],
                    reform_functions,
                    dynamic_functions,
                ),
            )

        metrics = compute_scenario_household_metrics(
            year=year,
            dataset_name=dataset_name,
            reform=reform,
        )
        gc.collect()

        metadata = _scenario_metadata(
            spec=spec,
            cell=cell,
            dataset_name=dataset_name,
        )
        _write_metrics_bundle(
            path_map=path_map,
            metrics=metrics,
            metadata=metadata,
        )
        _write_json_volume(
            path_map["success"],
            {
                "run_id": spec["run_id"],
                "year": year,
                "scenario_name": scenario,
                "reform_id": reform_id,
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "duration_seconds": round(time.time() - start_time, 3),
                "artifact_paths": {
                    key: str(value)
                    for key, value in path_map.items()
                    if key in {"metrics", "metadata"}
                },
            },
        )
        results_volume.commit()
        print(
            f"SAVED SCENARIO: run={spec['run_id']} year={year} "
            f"scenario={scenario} -> {_absolute_volume_path(path_map['metrics'])}"
        )
        return {
            "run_id": spec["run_id"],
            "year": year,
            "scenario_name": scenario,
            "status": "success",
        }
    except Exception:
        _write_json_volume(
            path_map["error"],
            {
                "run_id": spec["run_id"],
                "year": year,
                "scenario_name": scenario,
                "reform_id": reform_id,
                "failed_at": datetime.utcnow().isoformat() + "Z",
                "traceback": traceback.format_exc(),
            },
        )
        results_volume.commit()
        raise


@app.function(
    image=image,
    cpu=4,
    memory=32768,
    timeout=7200,
    volumes={"/results": results_volume},
)
def compute_year(
    year: int,
    reform_ids: list[str],
    scoring_type: str = "static",
    save_path: str | None = None,
) -> list[dict]:
    import gc
    import time
    import traceback
    import warnings

    warnings.filterwarnings("ignore")
    os.environ.setdefault("CRFB_DATASET_TEMPLATE", "/app/projected_datasets/{year}.h5")

    sys.path.insert(0, "/app/src")

    from runtime_config import dataset_path
    from year_runner import (
        MODAL_EMPLOYER_NET_REFORMS,
        MODAL_UNSUPPORTED_REFORMS,
        compute_reform_result,
        get_reform_lookups,
        load_baseline,
        load_household_weights,
    )

    print(f"\n{'=' * 60}")
    print(f"MODAL WORKER: Year {year} ({scoring_type.upper()} scoring)")
    print(f"Reforms: {', '.join(reform_ids)}")
    print(f"{'=' * 60}\n")

    unsupported = sorted(set(reform_ids) & MODAL_UNSUPPORTED_REFORMS)
    if unsupported:
        raise ValueError(
            "Unsupported reforms for modal_batch/compute.py: "
            + ", ".join(unsupported)
            + ". Use batch/run_option13_modal.py for option13/balanced_fix."
        )

    dataset_name = dataset_path(year)
    reform_functions, dynamic_functions = get_reform_lookups(MODAL_UNSUPPORTED_REFORMS)

    baseline_start = time.time()
    baseline = load_baseline(year, dataset_name)
    weight_household_ids, household_weights = load_household_weights(dataset_name)
    gc.collect()

    print(f"[1] Dataset: {dataset_name}")
    print(
        f"[2] Baseline: ${baseline.revenue / 1e9:.2f}B "
        f"(TOB OASDI: ${baseline.tob_oasdi / 1e9:.2f}B, "
        f"HI: ${baseline.tob_medicare_hi / 1e9:.2f}B, "
        f"{time.time() - baseline_start:.1f}s)"
    )

    results: list[dict] = []

    for index, reform_id in enumerate(reform_ids, start=1):
        reform_start = time.time()
        print(f"\n[{index + 2}] Computing {reform_id}...")

        try:
            result = compute_reform_result(
                reform_id=reform_id,
                year=year,
                scoring_type=scoring_type,
                dataset_name=dataset_name,
                baseline=baseline,
                reform_functions=reform_functions,
                dynamic_functions=dynamic_functions,
                employer_net_reforms=MODAL_EMPLOYER_NET_REFORMS,
                default_net_impact_mode="direct",
                weight_household_ids=weight_household_ids,
                household_weights=household_weights,
            )
        except Exception as error:
            print(f"    ERROR: {error}")
            traceback.print_exc()
            continue

        results.append(result)
        gc.collect()

        print(
            f"    Impact: ${float(result['revenue_impact']) / 1e9:+.2f}B "
            f"(OASDI: ${float(result['tob_oasdi_impact']) / 1e9:+.2f}B, "
            f"HI: ${float(result['tob_medicare_hi_impact']) / 1e9:+.2f}B, "
            f"{time.time() - reform_start:.1f}s)"
        )

        if save_path:
            volume_path = Path("/results") / save_path / f"year_{year}.csv"
            volume_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(results).to_csv(volume_path, index=False)
            results_volume.commit()
            print(f"    SAVED PARTIAL RESULTS TO VOLUME: {volume_path}")

    print(f"\n{'=' * 60}")
    print(f"COMPLETE: {len(results)} reforms for year {year}")
    print(f"{'=' * 60}\n")

    if save_path and results:
        volume_path = Path("/results") / save_path / f"year_{year}.csv"
        volume_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(results).to_csv(volume_path, index=False)
        results_volume.commit()
        print(f"SAVED TO VOLUME: {volume_path}")

    return results


@app.function(
    image=image,
    cpu=4,
    memory=65536,
    timeout=14400,
    volumes={"/results": results_volume},
)
def compute_cell(
    year: int,
    reform_id: str,
    scoring_type: str = "static",
    save_path: str | None = None,
) -> dict:
    import gc
    import time
    import traceback
    import warnings

    warnings.filterwarnings("ignore")
    os.environ.setdefault("CRFB_DATASET_TEMPLATE", "/app/projected_datasets/{year}.h5")

    sys.path.insert(0, "/app/src")

    from runtime_config import dataset_path
    from year_runner import (
        MODAL_EMPLOYER_NET_REFORMS,
        MODAL_UNSUPPORTED_REFORMS,
        compute_reform_result,
        get_reform_lookups,
        load_baseline,
        load_household_weights,
    )

    if reform_id in MODAL_UNSUPPORTED_REFORMS:
        raise ValueError(
            f"Unsupported reform for modal_batch/compute.py: {reform_id}. "
            "Use batch/run_option13_modal.py for option13/balanced_fix."
        )

    print(f"\n{'=' * 60}")
    print(f"MODAL CELL: {reform_id} for year {year} ({scoring_type.upper()} scoring)")
    print(f"{'=' * 60}\n")

    dataset_name = dataset_path(year)
    reform_functions, dynamic_functions = get_reform_lookups(MODAL_UNSUPPORTED_REFORMS)

    baseline_start = time.time()
    baseline = load_baseline(year, dataset_name)
    weight_household_ids, household_weights = load_household_weights(dataset_name)
    gc.collect()

    print(f"[1] Dataset: {dataset_name}")
    print(
        f"[2] Baseline: ${baseline.revenue / 1e9:.2f}B "
        f"(TOB OASDI: ${baseline.tob_oasdi / 1e9:.2f}B, "
        f"HI: ${baseline.tob_medicare_hi / 1e9:.2f}B, "
        f"{time.time() - baseline_start:.1f}s)"
    )

    reform_start = time.time()
    try:
        result = compute_reform_result(
            reform_id=reform_id,
            year=year,
            scoring_type=scoring_type,
            dataset_name=dataset_name,
            baseline=baseline,
            reform_functions=reform_functions,
            dynamic_functions=dynamic_functions,
            employer_net_reforms=MODAL_EMPLOYER_NET_REFORMS,
            default_net_impact_mode="direct",
            weight_household_ids=weight_household_ids,
            household_weights=household_weights,
        )
    except Exception:
        if save_path:
            _write_error_artifact(
                save_path,
                traceback.format_exc(),
            )
        raise
    gc.collect()

    print(
        f"[3] Impact: ${float(result['revenue_impact']) / 1e9:+.2f}B "
        f"(OASDI: ${float(result['tob_oasdi_impact']) / 1e9:+.2f}B, "
        f"HI: ${float(result['tob_medicare_hi_impact']) / 1e9:+.2f}B, "
        f"{time.time() - reform_start:.1f}s)"
    )

    if save_path:
        volume_path = Path("/results") / save_path
        volume_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([result]).to_csv(volume_path, index=False)
        results_volume.commit()
        print(f"SAVED TO VOLUME: {volume_path}")

    return result


@app.function(
    image=image,
    cpu=4,
    memory=65536,
    timeout=14400,
    volumes={"/results": results_volume},
)
def materialize_scenario_artifact(spec: dict, cell: dict) -> dict:
    return _materialize_scenario_impl(spec, cell)


@app.function(
    image=image,
    cpu=4,
    memory=65536,
    timeout=14400,
    volumes={"/results": results_volume},
)
def materialize_scenario_from_run(
    run_id: str,
    year: int,
    scenario_name: str,
    reform_id: str = "",
) -> dict:
    spec = _load_remote_run_manifest(run_id)
    cell = {
        "year": int(year),
        "scenario_name": scenario_name,
        "reform_id": reform_id or None,
    }
    return _materialize_scenario_impl(spec, cell)


@app.local_entrypoint()
def test_single(reform: str = "option9", year: int = 2030, scoring: str = "static"):
    """Test a single reform/year combination."""
    print(f"\nTesting {reform} for {year} ({scoring})...")
    results = compute_year.remote(year, [reform], scoring)

    for result in results:
        print(f"\n{result['reform_name']} ({result['year']}):")
        print(f"  Revenue impact: ${result['revenue_impact'] / 1e9:+.2f}B")
        print(f"  OASDI impact: ${result['tob_oasdi_impact'] / 1e9:+.2f}B")
        print(f"  Medicare HI impact: ${result['tob_medicare_hi_impact'] / 1e9:+.2f}B")


@app.local_entrypoint()
def sniff_test(reforms: str = "option9,option10,option11", scoring: str = "static"):
    """Quick sniff test: run 3 sample years (2030, 2050, 2080) for specified reforms."""
    reform_list = [reform.strip() for reform in reforms.split(",")]
    test_years = [2030, 2050, 2080]

    print(f"\nSniff test: {reform_list} for years {test_years}")
    print("=" * 60)

    args = [(year, reform_list, scoring) for year in test_years]
    all_results = []
    for result_batch in compute_year.starmap(args):
        all_results.extend(result_batch)

    print("\n" + "=" * 60)
    print("SNIFF TEST RESULTS")
    print("=" * 60)

    for reform_id in reform_list:
        print(f"\n{reform_id}:")
        for year in test_years:
            result = next(
                (
                    row
                    for row in all_results
                    if row["reform_name"] == reform_id and row["year"] == year
                ),
                None,
            )
            if result:
                print(
                    f"  {year}: ${result['revenue_impact'] / 1e9:+.2f}B "
                    f"(OASDI: ${result['tob_oasdi_impact'] / 1e9:+.2f}B)"
                )


@app.local_entrypoint()
def run_reforms(
    reforms: str = "option9,option10,option11",
    scoring: str = "dynamic",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
    resume: bool = True,
):
    """
    Run multiple reforms across all years in parallel (year-based parallelization).

    Saves intermediate results after each year completes, so interrupted runs
    can be resumed with --resume flag.
    """
    reform_list = [reform.strip() for reform in reforms.split(",")]

    year_list = _parse_years(years)

    output_path = Path(output)
    stem = _stem_with_scoring(output_path.stem, scoring)
    output_dir = output_path.parent / stem
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_save_path = f"{stem}_{run_id}"
    print(f"Volume save path: /results/{volume_save_path}/")

    completed_years = set()
    if resume:
        for file_path in output_dir.glob("year_*.csv"):
            try:
                completed_years.add(int(file_path.stem.split("_")[1]))
            except (IndexError, ValueError):
                continue

        if completed_years:
            print(f"Resuming: found {len(completed_years)} completed years")
            year_list = [year for year in year_list if year not in completed_years]
            if not year_list:
                print("All years already completed!")
                _combine_results(output_dir, output_path, reform_list)
                return

    print(f"\nRunning {len(reform_list)} reforms x {len(year_list)} years")
    print(f"= {len(year_list)} parallel tasks (one per year)")
    print(f"Reforms: {reform_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    print(f"Intermediate results: {output_dir}/")
    print(f"Volume backup: /results/{volume_save_path}/")

    args = [(year, reform_list, scoring, volume_save_path) for year in year_list]
    completed = 0
    job_failed = False

    try:
        for result_batch in compute_year.starmap(args):
            completed += 1
            if not result_batch:
                continue

            year = result_batch[0]["year"]
            year_file = output_dir / f"year_{year}.csv"
            pd.DataFrame(result_batch).to_csv(year_file, index=False)
            print(f"  [{completed}/{len(year_list)}] Year {year} saved to {year_file}")
    except Exception as error:
        print(f"\n{'=' * 60}")
        print(f"JOB FAILED: {error}")
        print(f"{'=' * 60}")
        print("\nBut results were saved to Modal Volume!")
        print("Downloading completed results from volume...")
        job_failed = True

    if job_failed:
        _download_from_volume(volume_save_path, output_dir)

    _combine_results(output_dir, output_path, reform_list)


@app.local_entrypoint()
def run_cells(
    reforms: str = "option9,option10,option11",
    scoring: str = "dynamic",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
    resume: bool = True,
):
    """
    Run one reform x one year per task.

    This isolates failures to individual cells and writes every completed cell
    to the Modal volume immediately.
    """
    reform_list = [reform.strip() for reform in reforms.split(",") if reform.strip()]

    year_list = _parse_years(years)

    output_path = Path(output)
    stem = _stem_with_scoring(output_path.stem, scoring)
    output_dir = output_path.parent / stem
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_save_path = f"{stem}_{run_id}"
    print(f"Volume save path: /results/{volume_save_path}/")

    pending_cells: list[tuple[str, int, Path]] = []
    for reform_id in reform_list:
        for year in year_list:
            local_file = output_dir / reform_id / f"year_{year}.csv"
            if resume and local_file.exists():
                continue
            pending_cells.append((reform_id, year, local_file))

    if not pending_cells:
        print("All cells already completed locally.")
        _combine_results_recursive(output_dir, output_path, reform_list)
        return

    print(f"\nRunning {len(pending_cells)} cells")
    print(f"Reforms: {reform_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    print(f"Intermediate results: {output_dir}/")
    print(f"Volume backup: /results/{volume_save_path}/")

    calls = []
    for reform_id, year, local_file in pending_cells:
        volume_file = f"{volume_save_path}/{reform_id}/year_{year}.csv"
        call = compute_cell.spawn(year, reform_id, scoring, volume_file)
        calls.append((reform_id, year, local_file, call))

    failures: list[tuple[str, int, str]] = []
    for index, (reform_id, year, local_file, call) in enumerate(calls, start=1):
        try:
            result = call.get(timeout=15000)
            local_file.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([result]).to_csv(local_file, index=False)
            print(f"  [{index}/{len(calls)}] Saved {reform_id} {year} to {local_file}")
        except Exception as error:
            failures.append((reform_id, year, str(error)))
            print(f"  [{index}/{len(calls)}] FAILED {reform_id} {year}: {error}")

    _download_from_volume(volume_save_path, output_dir)
    _combine_results_recursive(output_dir, output_path, reform_list)

    if failures:
        print("\nFailures:")
        for reform_id, year, message in failures:
            print(f"  - {reform_id} {year}: {message}")


@app.local_entrypoint()
def run_cells_detached(
    reforms: str = "option9,option10,option11",
    scoring: str = "dynamic",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
    resume: bool = True,
):
    """
    Submit one reform x one year per task and return immediately.

    This is the correct detached pattern for Modal batch work:
    enqueue all cells, write results to the Modal volume, and recover them later.
    It avoids keeping a local coordinator alive waiting on call.get().
    """
    reform_list = [reform.strip() for reform in reforms.split(",") if reform.strip()]
    year_list = _parse_years(years)

    output_path = Path(output)
    stem = _stem_with_scoring(output_path.stem, scoring)
    output_dir = output_path.parent / stem
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_save_path = f"{stem}_{run_id}"

    pending_cells: list[tuple[str, int]] = []
    for reform_id in reform_list:
        for year in year_list:
            local_file = output_dir / reform_id / f"year_{year}.csv"
            if resume and local_file.exists():
                continue
            pending_cells.append((reform_id, year))

    if not pending_cells:
        print("All cells already completed locally.")
        _combine_results_recursive(output_dir, output_path, reform_list)
        return

    manifest = {
        "mode": "run_cells_detached",
        "created_at": datetime.now().isoformat(),
        "scoring": scoring,
        "output_csv": str(output_path),
        "output_dir": str(output_dir),
        "volume_path": volume_save_path,
        "reforms": reform_list,
        "years": year_list,
        "pending_cells": [
            {"reform_id": reform_id, "year": year} for reform_id, year in pending_cells
        ],
    }
    manifest_path = output_dir / "_modal_detached_run.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nSubmitting {len(pending_cells)} detached cells")
    print(f"Reforms: {reform_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    print(f"Local manifest: {manifest_path}")
    print(f"Volume backup: /results/{volume_save_path}/")
    print("Recovery command:")
    print(
        "  uv run python scripts/recover_modal_results.py "
        f"--volume-path {volume_save_path} --output-dir {output_dir}"
    )

    years_iter = (year for _, year in pending_cells)
    reforms_iter = (reform_id for reform_id, _ in pending_cells)
    scoring_iter = itertools.repeat(scoring, len(pending_cells))
    volume_paths_iter = (
        f"{volume_save_path}/{reform_id}/year_{year}.csv"
        for reform_id, year in pending_cells
    )
    compute_cell.spawn_map(
        years_iter,
        reforms_iter,
        scoring_iter,
        volume_paths_iter,
    )


def _download_from_volume(volume_path: str, output_dir: Path) -> None:
    print(f"\nDownloading from volume: {volume_path}")

    result = subprocess.run(
        [*modal_cli_prefix(), "volume", "ls", "crfb-results", volume_path],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"Volume contents:\n{result.stdout}")

    result = subprocess.run(
        [
            *modal_cli_prefix(),
            "volume",
            "get",
            "crfb-results",
            f"{volume_path}/",
            str(output_dir) + "/",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        print(f"Downloaded to {output_dir}/")
    else:
        print(f"Download error: {result.stderr}")

    downloaded = list(output_dir.rglob("year_*.csv"))
    print(f"Downloaded {len(downloaded)} year files")


def _combine_results(
    output_dir: Path,
    output_path: Path,
    reform_list: list[str],
) -> None:
    all_files = sorted(output_dir.glob("year_*.csv"))
    if not all_files:
        print("No results to combine!")
        return

    df = pd.concat(
        [pd.read_csv(file_path) for file_path in all_files], ignore_index=True
    )
    df = df.sort_values(["reform_name", "year"])
    df.to_csv(output_path, index=False)

    print(f"\nCombined {len(all_files)} year files into {output_path}")
    print(f"Total results: {len(df)} rows")

    print("\n" + "=" * 60)
    print("SUMMARY (totals across computed years)")
    print("=" * 60)
    for reform_id in reform_list:
        reform_df = df[df["reform_name"] == reform_id]
        if len(reform_df) == 0:
            continue

        total_impact = reform_df["revenue_impact"].sum() / 1e9
        oasdi_impact = reform_df["tob_oasdi_impact"].sum() / 1e9
        hi_impact = reform_df["tob_medicare_hi_impact"].sum() / 1e9
        print(
            f"{reform_id}: ${total_impact:+,.1f}B total "
            f"(OASDI: ${oasdi_impact:+,.1f}B, HI: ${hi_impact:+,.1f}B)"
        )


def _combine_results_recursive(
    output_dir: Path,
    output_path: Path,
    reform_list: list[str],
) -> None:
    all_files = sorted(output_dir.rglob("year_*.csv"))
    if not all_files:
        print("No results to combine!")
        return

    df = pd.concat(
        [pd.read_csv(file_path) for file_path in all_files], ignore_index=True
    )
    df = df.sort_values(["reform_name", "year"])
    df.to_csv(output_path, index=False)

    print(f"\nCombined {len(all_files)} cell files into {output_path}")
    print(f"Total results: {len(df)} rows")

    print("\n" + "=" * 60)
    print("SUMMARY (totals across computed years)")
    print("=" * 60)
    for reform_id in reform_list:
        reform_df = df[df["reform_name"] == reform_id]
        if len(reform_df) == 0:
            continue

        total_impact = reform_df["revenue_impact"].sum() / 1e9
        oasdi_impact = reform_df["tob_oasdi_impact"].sum() / 1e9
        hi_impact = reform_df["tob_medicare_hi_impact"].sum() / 1e9
        print(
            f"{reform_id}: ${total_impact:+,.1f}B total "
            f"(OASDI: ${oasdi_impact:+,.1f}B, HI: ${hi_impact:+,.1f}B)"
        )


@app.local_entrypoint()
def list_volume_results():
    """List all saved results in the Modal volume."""
    print("\nResults saved in Modal volume 'crfb-results':")
    print("=" * 60)

    result = subprocess.run(
        ["modal", "volume", "ls", "crfb-results"],
        capture_output=True,
        text=True,
        check=False,
    )
    print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}")


@app.local_entrypoint()
def recover_results(
    volume_path: str,
    output: str = "results/recovered/",
):
    """
    Recover results from a failed job that saved to Modal volume.

    Args:
        volume_path: The volume path from a previous run (shown in job output)
        output: Local directory to download results to
    """
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _download_from_volume(volume_path, output_dir)

    files = sorted(output_dir.rglob("year_*.csv"))
    print(f"\nRecovered {len(files)} result files:")
    for file_path in files:
        print(f"  {file_path.name}")

    error_files = sorted(output_dir.rglob("*.error.txt"))
    if error_files:
        print(f"\nRecovered {len(error_files)} error files:")
        for error_path in error_files:
            print(f"  {error_path}")

    reform_list = _recursive_reform_list(output_dir)
    if reform_list:
        combined_path = output_dir.with_suffix(".csv")
        _combine_results_recursive(output_dir, combined_path, reform_list)
