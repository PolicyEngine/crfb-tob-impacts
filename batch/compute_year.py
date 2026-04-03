#!/usr/bin/env python3
# ruff: noqa: E402
"""
Year-based Worker: Compute all reforms for a single year in one task.

This is the CORRECT architecture:
- Download dataset ONCE per year
- Calculate baseline ONCE per year
- Run ALL reforms for that year
- Parallelize by YEAR, not by reform

Usage:
    python compute_year.py YEAR SCORING_TYPE BUCKET_NAME JOB_ID [REFORMS...]

Arguments:
    YEAR: Year to compute (e.g., 2026)
    SCORING_TYPE: 'static' or 'dynamic'
    BUCKET_NAME: Cloud Storage bucket name
    JOB_ID: Unique job identifier
    REFORMS: Space-separated list of reform IDs (e.g., 'option1 option2 option3 option4')
"""

from __future__ import annotations

import gc
import os
import sys
import time
import traceback
import warnings
from pathlib import Path

import pandas as pd
from google.cloud import storage

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[1]

local_policyengine_us = os.environ.get("CRFB_POLICYENGINE_US_PATH")
vendored_policyengine_us = PROJECT_ROOT / "policyengine-us"

path_candidates = [PROJECT_ROOT / "src", Path("/app/src")]
if local_policyengine_us:
    path_candidates.append(Path(local_policyengine_us))
if vendored_policyengine_us.exists():
    path_candidates.append(vendored_policyengine_us)

for path in reversed(path_candidates):
    if path.exists():
        sys.path.insert(0, str(path))

from runtime_config import dataset_path
from year_runner import (
    BATCH_EMPLOYER_NET_REFORMS,
    SPECIAL_BASELINE_REFORMS,
    compute_reform_result,
    get_reform_lookups,
    load_baseline,
)


def upload_results(
    bucket: storage.Bucket,
    csv_path: str,
    results: list[dict[str, float | int | str]],
) -> None:
    df = pd.DataFrame(results)
    blob = bucket.blob(csv_path)
    blob.upload_from_string(df.to_csv(index=False), content_type="text/csv")


def main() -> None:
    if len(sys.argv) < 5:
        print(
            "Usage: python compute_year.py YEAR SCORING_TYPE BUCKET_NAME JOB_ID [REFORMS...]"
        )
        sys.exit(1)

    year = int(sys.argv[1])
    scoring_type = sys.argv[2]
    bucket_name = sys.argv[3]
    job_id = sys.argv[4]

    reform_functions, dynamic_functions = get_reform_lookups()
    reform_ids = sys.argv[5:] if len(sys.argv) > 5 else list(reform_functions.keys())
    unsupported = sorted(set(reform_ids) & SPECIAL_BASELINE_REFORMS)
    if unsupported:
        print(
            "Use batch/run_option13_modal.py for special baseline reforms: "
            + ", ".join(unsupported)
        )
        sys.exit(1)

    print(f"\n{'=' * 80}")
    print(f"YEAR-BASED WORKER: {year} ({scoring_type.upper()} scoring)")
    print(f"{'=' * 80}")
    print(f"Reforms to compute: {', '.join(reform_ids)}")
    print(f"Total reforms: {len(reform_ids)}")
    print(f"Job ID: {job_id}")
    print(f"Bucket: {bucket_name}")

    dataset_name = dataset_path(year)
    print(f"\nDataset: {dataset_name}")

    baseline_start = time.time()
    baseline = load_baseline(year, dataset_name)
    gc.collect()
    print(
        f"Baseline: ${baseline.revenue / 1e9:.2f}B "
        f"(TOB OASDI: ${baseline.tob_oasdi / 1e9:.2f}B, "
        f"HI: ${baseline.tob_medicare_hi / 1e9:.2f}B, "
        f"{time.time() - baseline_start:.1f}s)"
    )

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    if len(reform_ids) == 1:
        csv_path = f"results/{job_id}/{year}_{reform_ids[0]}_{scoring_type}_results.csv"
    else:
        csv_path = f"results/{job_id}/{year}_{scoring_type}_results.csv"

    results: list[dict[str, float | int | str]] = []

    for index, reform_id in enumerate(reform_ids, start=1):
        print(f"\n[{index}/{len(reform_ids)}] Computing {reform_id}...")
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
                employer_net_reforms=BATCH_EMPLOYER_NET_REFORMS,
                default_net_impact_mode="direct",
            )
        except Exception as error:
            print(f"Failed to compute {reform_id}: {error}")
            traceback.print_exc()
            continue

        results.append(result)
        gc.collect()

        print(
            f"Impact: ${float(result['revenue_impact']) / 1e9:+.2f}B "
            f"(OASDI: ${float(result['tob_oasdi_impact']) / 1e9:+.2f}B, "
            f"HI: ${float(result['tob_medicare_hi_impact']) / 1e9:+.2f}B, "
            f"{time.time() - reform_start:.1f}s)"
        )

        if len(reform_ids) > 1:
            try:
                upload_results(bucket, csv_path, results)
                print(
                    f"Saved {len(results)}/{len(reform_ids)} reforms to "
                    f"gs://{bucket_name}/{csv_path}"
                )
            except Exception as error:
                print(f"Warning: incremental save failed: {error}")

    if not results:
        print("No results computed.")
        sys.exit(1)

    try:
        upload_results(bucket, csv_path, results)
    except Exception as error:
        print(f"Failed to save final results: {error}")
        traceback.print_exc()
        sys.exit(1)

    print(f"\nSaved final results to gs://{bucket_name}/{csv_path}")
    print(f"{'=' * 80}")
    print(f"YEAR {year} COMPLETE: {len(results)} reforms")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
