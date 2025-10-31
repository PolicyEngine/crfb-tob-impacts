#!/usr/bin/env python3
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

import sys
import time
import gc
import warnings
warnings.filterwarnings('ignore')

# Add src to path for imports
sys.path.insert(0, '/app/src')

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
from google.cloud import storage
import pandas as pd

# Import reform functions
from reforms import (
    get_option1_reform,
    get_option2_reform,
    get_option3_reform,
    get_option4_reform,
    get_option5_reform,
    get_option6_reform,
    get_option7_reform,
    get_option8_reform
)

REFORM_FUNCTIONS = {
    'option1': get_option1_reform,
    'option2': get_option2_reform,
    'option3': get_option3_reform,
    'option4': get_option4_reform,
    'option5': get_option5_reform,
    'option6': get_option6_reform,
    'option7': get_option7_reform,
    'option8': get_option8_reform,
}

# CBO labor supply elasticities for dynamic scoring
CBO_LABOR_PARAMS = {
    "gov.simulation.labor_supply_responses.elasticities.income": {
        "2024-01-01.2100-12-31": -0.05
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.1": {
        "2024-01-01.2100-12-31": 0.31
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.2": {
        "2024-01-01.2100-12-31": 0.28
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.3": {
        "2024-01-01.2100-12-31": 0.27
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.4": {
        "2024-01-01.2100-12-31": 0.27
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.5": {
        "2024-01-01.2100-12-31": 0.25
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.6": {
        "2024-01-01.2100-12-31": 0.25
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.7": {
        "2024-01-01.2100-12-31": 0.22
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.8": {
        "2024-01-01.2100-12-31": 0.19
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.9": {
        "2024-01-01.2100-12-31": 0.15
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.10": {
        "2024-01-01.2100-12-31": 0.10
    }
}


def get_reform_dict(reform_func):
    """Extract reform dictionary from a reform function."""
    reform_obj = reform_func()
    if isinstance(reform_obj, dict):
        return reform_obj
    elif isinstance(reform_obj, Reform):
        return reform_obj.data
    else:
        raise ValueError(f"Unexpected reform type: {type(reform_obj)}")


def main():
    if len(sys.argv) < 5:
        print("Usage: python compute_year.py YEAR SCORING_TYPE BUCKET_NAME JOB_ID [REFORMS...]")
        sys.exit(1)

    year = int(sys.argv[1])
    scoring_type = sys.argv[2]
    bucket_name = sys.argv[3]
    job_id = sys.argv[4]
    reform_ids = sys.argv[5:] if len(sys.argv) > 5 else list(REFORM_FUNCTIONS.keys())

    print(f"\n{'='*80}")
    print(f"YEAR-BASED WORKER: {year} ({scoring_type.upper()} scoring)")
    print(f"{'='*80}")
    print(f"Reforms to compute: {', '.join(reform_ids)}")
    print(f"Total reforms: {len(reform_ids)}")
    print()

    # Step 1: Download dataset ONCE
    print(f"[1/{3+len(reform_ids)}] Downloading dataset for {year}...")
    dataset_start = time.time()
    dataset_name = f"hf://policyengine/test/{year}.h5"
    print(f"      Dataset: {dataset_name}")
    dataset_time = time.time() - dataset_start
    print(f"      ✓ Dataset reference prepared ({dataset_time:.1f}s)")
    print()

    # Step 2: Calculate baseline ONCE (with detailed timing)
    print(f"[2/{3+len(reform_ids)}] Creating baseline simulation for {year}...")
    baseline_start = time.time()
    try:
        create_start = time.time()
        baseline_sim = Microsimulation(dataset=dataset_name)
        create_time = time.time() - create_start
        print(f"      - Microsimulation created: {create_time:.1f}s")

        calc_start = time.time()
        baseline_income_tax = baseline_sim.calculate("income_tax", map_to="household", period=year)
        calc_time = time.time() - calc_start
        print(f"      - Income tax calculated: {calc_time:.1f}s")

        baseline_revenue = float(baseline_income_tax.sum())
        baseline_time = time.time() - baseline_start
        print(f"      ✓ Baseline calculated: ${baseline_revenue/1e9:.2f}B (total: {baseline_time:.1f}s)")

        # Clean up baseline objects immediately after extracting the value
        del baseline_sim
        del baseline_income_tax
        gc.collect()
        print(f"      ✓ Baseline objects cleaned up")
    except Exception as e:
        print(f"      ✗ Baseline calculation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    print()

    # Step 3: Run ALL reforms for this year (save each result incrementally)
    results = []
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    csv_path = f"results/{job_id}/{year}_{scoring_type}_results.csv"

    for i, reform_id in enumerate(reform_ids, start=1):
        print(f"[{2+i}/{3+len(reform_ids)}] Computing {reform_id} for {year}...")
        reform_start = time.time()

        try:
            # Get reform function
            reform_func = REFORM_FUNCTIONS.get(reform_id)
            if not reform_func:
                print(f"      ✗ Unknown reform: {reform_id}")
                continue

            # Create reform based on scoring type
            if scoring_type == 'static':
                reform = reform_func()
                print(f"      ✓ Static reform created")
            elif scoring_type == 'dynamic':
                reform_dict = get_reform_dict(reform_func)
                combined_dict = {**reform_dict, **CBO_LABOR_PARAMS}
                reform = Reform.from_dict(combined_dict, country_id="us")
                print(f"      ✓ Dynamic reform with CBO elasticities")
            else:
                print(f"      ✗ Invalid scoring type: {scoring_type}")
                continue

            # Run simulation with detailed timing
            print(f"      Running PolicyEngine simulation...")
            sim_start = time.time()

            create_start = time.time()
            reform_sim = Microsimulation(reform=reform, dataset=dataset_name)
            create_time = time.time() - create_start
            print(f"        - Microsimulation object created: {create_time:.1f}s")

            calc_start = time.time()
            reform_income_tax = reform_sim.calculate("income_tax", map_to="household", period=year)
            calc_time = time.time() - calc_start
            print(f"        - Income tax calculated: {calc_time:.1f}s")

            reform_revenue = float(reform_income_tax.sum())
            sim_time = time.time() - sim_start

            # Calculate impact
            impact = reform_revenue - baseline_revenue

            reform_time = time.time() - reform_start
            print(f"      ✓ Reform revenue: ${reform_revenue/1e9:.2f}B")
            print(f"      ✓ Impact: ${impact/1e9:+.2f}B ({reform_time:.1f}s total, {sim_time:.1f}s simulation)")

            # Store result (include baseline for reference)
            result = {
                'reform_name': reform_id,
                'year': year,
                'baseline_revenue': baseline_revenue,
                'reform_revenue': reform_revenue,
                'revenue_impact': impact,
                'scoring_type': scoring_type
            }
            results.append(result)

            # CRITICAL: Clean up reform objects immediately to prevent memory accumulation
            del reform_sim
            del reform_income_tax
            del reform
            gc.collect()
            print(f"      ✓ Memory cleaned up")

            # Save incrementally to Cloud Storage
            try:
                df = pd.DataFrame(results)
                blob = bucket.blob(csv_path)
                blob.upload_from_string(df.to_csv(index=False), content_type='text/csv')
                print(f"      ✓ Saved to gs://{bucket_name}/{csv_path} ({len(results)} reforms)")
            except Exception as save_error:
                print(f"      ⚠ Warning: Failed to save intermediate results: {save_error}")
                # Don't fail the whole job if intermediate save fails
                pass

        except Exception as e:
            print(f"      ✗ Reform calculation failed: {e}")
            import traceback
            traceback.print_exc()

        print()

    # Step 4: Final verification
    print(f"[{3+len(reform_ids)}/{3+len(reform_ids)}] Verifying final results...")

    if not results:
        print("      ✗ No results computed!")
        sys.exit(1)

    # Final save to Cloud Storage (already saved incrementally, but do one final write)
    try:
        df = pd.DataFrame(results)
        blob = bucket.blob(csv_path)
        blob.upload_from_string(df.to_csv(index=False), content_type='text/csv')
        print(f"      ✓ Final results saved to gs://{bucket_name}/{csv_path}")
        print(f"      ✓ Total reforms: {len(results)}")

    except Exception as e:
        print(f"      ✗ Failed to save final results: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)  # Exit with error so Cloud Batch marks task as FAILED

    print()
    print(f"{'='*80}")
    print(f"✓ YEAR {year} COMPLETE")
    print(f"{'='*80}")
    print(f"Total reforms computed: {len(results)}")
    print(f"Total time: {sum(r['total_time'] for r in results):.1f}s")
    print(f"Average time per reform: {sum(r['total_time'] for r in results)/len(results):.1f}s")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
