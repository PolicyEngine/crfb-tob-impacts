#!/usr/bin/env python3
"""
Phase 1 Worker: Compute baseline for a single year.

This script calculates the baseline income tax total for one year using
PolicyEngine's year-specific dataset.

Usage:
    python compute_baseline.py YEAR BUCKET_NAME

Arguments:
    YEAR: The year to compute baseline for (e.g., 2026)
    BUCKET_NAME: Cloud Storage bucket name for saving results
"""

import sys
import json
import warnings
warnings.filterwarnings('ignore')

def compute_baseline(year, bucket_name):
    """Compute baseline income tax total for a single year."""
    print(f"=" * 80)
    print(f"BASELINE CALCULATION: Year {year}")
    print(f"=" * 80)

    try:
        # Import PolicyEngine (done inside function to show timing)
        print(f"[1/4] Importing PolicyEngine...")
        from policyengine_us import Microsimulation
        from google.cloud import storage

        # Create baseline simulation with HuggingFace dataset
        print(f"[2/4] Creating baseline simulation for {year}...")
        dataset_name = f"hf://policyengine/test/{year}.h5"
        print(f"      Using dataset: {dataset_name}")
        baseline_sim = Microsimulation(dataset=dataset_name)

        # Calculate baseline income tax
        print(f"[3/4] Calculating income tax...")
        baseline_income_tax = baseline_sim.calculate(
            "income_tax",
            map_to="household",
            period=year
        )
        baseline_total = float(baseline_income_tax.sum())

        print(f"      ✓ Baseline total: ${baseline_total:,.0f}")
        print(f"      ✓ Baseline total: ${baseline_total/1e9:.2f}B")

        # Save to Cloud Storage
        print(f"[4/4] Saving to Cloud Storage...")
        result = {
            'year': year,
            'baseline_total': baseline_total
        }

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(f"baselines/{year}.json")
        blob.upload_from_string(json.dumps(result, indent=2))

        print(f"      ✓ Saved to: gs://{bucket_name}/baselines/{year}.json")
        print(f"\n{'=' * 80}")
        print(f"✓ SUCCESS: Baseline {year} completed")
        print(f"{'=' * 80}\n")

        return result

    except Exception as e:
        print(f"\n{'=' * 80}")
        print(f"✗ ERROR: Baseline {year} failed")
        print(f"{'=' * 80}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compute_baseline.py YEAR BUCKET_NAME")
        print("Example: python compute_baseline.py 2026 crfb-ss-analysis-results")
        sys.exit(1)

    year = int(sys.argv[1])
    bucket_name = sys.argv[2]

    compute_baseline(year, bucket_name)
