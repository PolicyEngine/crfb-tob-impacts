#!/usr/bin/env python3
"""
Results Download Script: Download and combine results from Cloud Storage.

This script downloads all result files from a completed Cloud Batch job,
combines them into DataFrames, and saves as CSV files.

Usage:
    python download_results.py --job-id JOB_ID [--bucket BUCKET] [--output-dir OUTPUT_DIR]

Examples:
    # Download results from specific job
    python download_results.py --job-id reforms-20251028-123456-abc123

    # Save to custom directory
    python download_results.py --job-id reforms-20251028-123456-abc123 --output-dir ../data/
"""

import argparse
import json
import os
from google.cloud import storage
import pandas as pd


# Configuration
DEFAULT_BUCKET = "crfb-ss-analysis-results"
DEFAULT_OUTPUT_DIR = "../data"


def download_results(bucket_name, job_id, output_dir):
    """Download and combine all results from a completed job."""

    print(f"\n{'=' * 80}")
    print(f"DOWNLOADING RESULTS")
    print(f"{'=' * 80}")
    print(f"Job ID: {job_id}")
    print(f"Bucket: gs://{bucket_name}/")
    print(f"Output directory: {output_dir}/")
    print(f"{'=' * 80}\n")

    # Connect to Cloud Storage
    print(f"[1/5] Connecting to Cloud Storage...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    # List all result files for this job
    print(f"[2/5] Listing result files...")
    prefix = f"results/{job_id}/"
    blobs = list(bucket.list_blobs(prefix=prefix))

    if not blobs:
        print(f"\n✗ ERROR: No results found for job {job_id}")
        print(f"   Make sure the job completed successfully and the job ID is correct.")
        print(f"   Check: gs://{bucket_name}/results/{job_id}/")
        return False

    print(f"      ✓ Found {len(blobs)} result files")

    # Download and parse all results
    print(f"[3/5] Downloading and parsing results...")
    results = []
    errors = []

    for i, blob in enumerate(blobs, 1):
        if i % 50 == 0:
            print(f"      Progress: {i}/{len(blobs)} files...")

        try:
            content = blob.download_as_string()
            result = json.loads(content)
            results.append(result)
        except Exception as e:
            errors.append((blob.name, str(e)))

    if errors:
        print(f"\n      ⚠ Warning: {len(errors)} files failed to parse:")
        for filename, error in errors[:5]:  # Show first 5 errors
            print(f"        - {filename}: {error}")
        if len(errors) > 5:
            print(f"        ... and {len(errors) - 5} more")

    print(f"      ✓ Successfully parsed {len(results)} results")

    if not results:
        print(f"\n✗ ERROR: No valid results found")
        return False

    # Convert to DataFrame
    print(f"[4/5] Creating DataFrames...")
    df = pd.DataFrame(results)

    # Check for required columns
    required_cols = ['reform_id', 'reform_name', 'year', 'scoring_type',
                     'baseline_total', 'reform_total', 'revenue_impact']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"\n✗ ERROR: Missing required columns: {missing_cols}")
        return False

    # Split into static and dynamic DataFrames
    static_df = df[df['scoring_type'] == 'static'].copy()
    dynamic_df = df[df['scoring_type'] == 'dynamic'].copy()

    # Sort by reform_id and year
    static_df = static_df.sort_values(['reform_id', 'year']).reset_index(drop=True)
    dynamic_df = dynamic_df.sort_values(['reform_id', 'year']).reset_index(drop=True)

    print(f"      ✓ Static results: {len(static_df)} rows")
    print(f"      ✓ Dynamic results: {len(dynamic_df)} rows")

    # Save to CSV
    print(f"[5/5] Saving CSV files...")
    os.makedirs(output_dir, exist_ok=True)

    static_path = os.path.join(output_dir, 'policy_impacts_static.csv')
    dynamic_path = os.path.join(output_dir, 'policy_impacts_dynamic.csv')
    combined_path = os.path.join(output_dir, 'policy_impacts_all.csv')

    static_df.to_csv(static_path, index=False)
    dynamic_df.to_csv(dynamic_path, index=False)
    df.to_csv(combined_path, index=False)

    print(f"      ✓ Saved: {static_path}")
    print(f"      ✓ Saved: {dynamic_path}")
    print(f"      ✓ Saved: {combined_path}")

    # Print summary statistics
    print(f"\n{'=' * 80}")
    print(f"SUMMARY STATISTICS")
    print(f"{'=' * 80}\n")

    # 10-year totals (2026-2035)
    df_10yr = df[df['year'].between(2026, 2035)]

    if len(df_10yr) > 0:
        print("10-Year Revenue Impacts (2026-2035, in Billions):\n")

        for scoring in ['static', 'dynamic']:
            df_scoring = df_10yr[df_10yr['scoring_type'] == scoring]
            if len(df_scoring) > 0:
                print(f"{scoring.upper()} SCORING:")
                totals = df_scoring.groupby(['reform_id', 'reform_name'])['revenue_impact'].sum() / 1e9

                for (reform_id, reform_name), total in totals.items():
                    print(f"  {reform_id}: ${total:>8.1f}B  ({reform_name})")
                print()

    # Coverage check
    print(f"Coverage Check:")
    print(f"  Unique reforms: {df['reform_id'].nunique()}")
    print(f"  Unique years: {df['year'].nunique()} ({df['year'].min()}-{df['year'].max()})")
    print(f"  Scoring types: {', '.join(df['scoring_type'].unique())}")

    expected_total = df['reform_id'].nunique() * df['year'].nunique() * df['scoring_type'].nunique()
    actual_total = len(df)
    print(f"  Expected rows: {expected_total}")
    print(f"  Actual rows: {actual_total}")

    if actual_total < expected_total:
        print(f"\n  ⚠ Warning: Missing {expected_total - actual_total} results")
        print(f"     Some reform-year-scoring combinations may have failed.")
    else:
        print(f"\n  ✓ All expected results present!")

    print(f"\n{'=' * 80}")
    print(f"✓ DOWNLOAD COMPLETE")
    print(f"{'=' * 80}\n")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download and combine results from Cloud Batch job"
    )
    parser.add_argument(
        '--job-id',
        type=str,
        required=True,
        help='Job ID from submit_reforms.py output'
    )
    parser.add_argument(
        '--bucket',
        type=str,
        default=DEFAULT_BUCKET,
        help=f'Cloud Storage bucket name (default: {DEFAULT_BUCKET})'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f'Output directory for CSV files (default: {DEFAULT_OUTPUT_DIR})'
    )

    args = parser.parse_args()

    try:
        success = download_results(args.bucket, args.job_id, args.output_dir)
        return 0 if success else 1
    except Exception as e:
        print(f"\n{'=' * 80}")
        print(f"✗ ERROR")
        print(f"{'=' * 80}")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
