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
import os
from pathlib import Path
import subprocess
import sys

import modal
import pandas as pd


LOCAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_PROJECT_ROOT = Path("/app")

path_candidates = [LOCAL_PROJECT_ROOT / "src", CONTAINER_PROJECT_ROOT / "src"]
for path in reversed(path_candidates):
    if path.exists():
        sys.path.insert(0, str(path))

from runtime_config import resolve_policyengine_us_path, resolve_projected_datasets_path


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
)


def _stem_with_scoring(stem: str, scoring: str) -> str:
    suffix = f"_{scoring}"
    return stem if stem.endswith(suffix) else f"{stem}{suffix}"


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

    if "-" in years:
        start, end = years.split("-")
        year_list = list(range(int(start), int(end) + 1))
    else:
        year_list = [int(year.strip()) for year in years.split(",")]

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

    if "-" in years:
        start, end = years.split("-")
        year_list = list(range(int(start), int(end) + 1))
    else:
        year_list = [int(year.strip()) for year in years.split(",") if year.strip()]

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
            print(
                f"  [{index}/{len(calls)}] Saved {reform_id} {year} to {local_file}"
            )
        except Exception as error:
            failures.append((reform_id, year, str(error)))
            print(f"  [{index}/{len(calls)}] FAILED {reform_id} {year}: {error}")

    _download_from_volume(volume_save_path, output_dir)
    _combine_results_recursive(output_dir, output_path, reform_list)

    if failures:
        print("\nFailures:")
        for reform_id, year, message in failures:
            print(f"  - {reform_id} {year}: {message}")


def _download_from_volume(volume_path: str, output_dir: Path) -> None:
    print(f"\nDownloading from volume: {volume_path}")

    result = subprocess.run(
        [
            "uvx",
            "--from",
            "modal",
            "--with",
            "pandas",
            "modal",
            "volume",
            "ls",
            "crfb-results",
            volume_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"Volume contents:\n{result.stdout}")

    result = subprocess.run(
        [
            "uvx",
            "--from",
            "modal",
            "--with",
            "pandas",
            "modal",
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

    df = pd.concat([pd.read_csv(file_path) for file_path in all_files], ignore_index=True)
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

    df = pd.concat([pd.read_csv(file_path) for file_path in all_files], ignore_index=True)
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

    files = sorted(output_dir.glob("year_*.csv"))
    print(f"\nRecovered {len(files)} year files:")
    for file_path in files:
        print(f"  {file_path.name}")
