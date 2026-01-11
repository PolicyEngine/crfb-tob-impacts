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

# Import reform functions (for static scoring - return Reform classes)
from reforms import (
    get_option1_reform,
    get_option2_reform,
    get_option3_reform,
    get_option4_reform,
    get_option5_reform,
    get_option6_reform,
    get_option7_reform,
    get_option8_reform,
    get_option9_reform,
    get_option10_reform,
    get_option11_reform,
)

# Import dict-returning functions (for dynamic scoring) from reforms.py
from reforms import (
    get_option1_dict,
    get_option2_dict,
    get_option3_dict,
    get_option4_dict,
    get_option5_dict,
    get_option6_dict,
    get_option7_dict,
    get_option8_dict,
    get_option9_dict,
    get_option10_dict,
    get_option11_dict,
    # Complete dynamic dicts with CBO elasticities pre-merged
    get_option1_dynamic_dict,
    get_option2_dynamic_dict,
    get_option3_dynamic_dict,
    get_option4_dynamic_dict,
    get_option5_dynamic_dict,
    get_option6_dynamic_dict,
    get_option7_dynamic_dict,
    get_option8_dynamic_dict,
    get_option9_dynamic_dict,
    get_option10_dynamic_dict,
    get_option11_dynamic_dict,
)

# Reform functions for static scoring (return Reform classes)
REFORM_FUNCTIONS = {
    'option1': get_option1_reform,
    'option2': get_option2_reform,
    'option3': get_option3_reform,
    'option4': get_option4_reform,
    'option5': get_option5_reform,
    'option6': get_option6_reform,
    'option7': get_option7_reform,
    'option8': get_option8_reform,
    'option9': get_option9_reform,
    'option10': get_option10_reform,
    'option11': get_option11_reform,
}

# Dict-returning functions for dynamic scoring with CBO elasticities
REFORM_DYNAMIC_DICT_FUNCTIONS = {
    'option1': get_option1_dynamic_dict,
    'option2': get_option2_dynamic_dict,
    'option3': get_option3_dynamic_dict,
    'option4': get_option4_dynamic_dict,
    'option5': get_option5_dynamic_dict,
    'option6': get_option6_dynamic_dict,
    'option7': get_option7_dynamic_dict,
    'option8': get_option8_dynamic_dict,
    'option9': get_option9_dynamic_dict,
    'option10': get_option10_dynamic_dict,
    'option11': get_option11_dynamic_dict,
}

# CBO labor supply elasticities for dynamic scoring
CBO_LABOR_PARAMS = {
    "gov.simulation.labor_supply_responses.elasticities.income.all": {
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
    elif isinstance(reform_obj, type) and issubclass(reform_obj, Reform):
        # Reform class - need to get parameter_values
        return reform_obj.parameter_values
    else:
        raise ValueError(f"Unexpected reform type: {type(reform_obj)}")


def main():
    print("\n" + "="*80)
    print("DIAGNOSTIC LOGGING: Script started")
    print(f"System time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python version: {sys.version}")
    print("="*80 + "\n")

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
    print(f"Job ID: {job_id}")
    print(f"Bucket: {bucket_name}")
    print()

    # Step 1: Download dataset ONCE
    print(f"[1/{3+len(reform_ids)}] Downloading dataset for {year}...")
    print(f"      DIAGNOSTIC: About to create dataset reference...")
    dataset_start = time.time()
    dataset_name = f"hf://policyengine/test/no-h6/{year}.h5"
    print(f"      Dataset: {dataset_name}")
    dataset_time = time.time() - dataset_start
    print(f"      ✓ Dataset reference prepared ({dataset_time:.1f}s)")
    print(f"      DIAGNOSTIC: Dataset reference created successfully")
    print()

    # Step 2: Calculate baseline ONCE (with detailed timing)
    print(f"[2/{3+len(reform_ids)}] Creating baseline simulation for {year}...")
    print(f"      DIAGNOSTIC: About to create Microsimulation object...")
    baseline_start = time.time()
    try:
        create_start = time.time()
        print(f"      DIAGNOSTIC: Calling Microsimulation(dataset='{dataset_name}')...")
        baseline_sim = Microsimulation(dataset=dataset_name)
        create_time = time.time() - create_start
        print(f"      - Microsimulation created: {create_time:.1f}s")
        print(f"      DIAGNOSTIC: Microsimulation object created successfully")

        calc_start = time.time()
        print(f"      DIAGNOSTIC: About to calculate income_tax...")
        baseline_income_tax = baseline_sim.calculate("income_tax", map_to="household", period=year)
        calc_time = time.time() - calc_start
        print(f"      - Income tax calculated: {calc_time:.1f}s")
        print(f"      DIAGNOSTIC: Income tax calculation complete")

        # Calculate TOB revenue variables
        print(f"      DIAGNOSTIC: About to calculate TOB revenue variables...")
        tob_start = time.time()
        baseline_tob_medicare = baseline_sim.calculate("tob_revenue_medicare_hi", map_to="household", period=year)
        baseline_tob_oasdi = baseline_sim.calculate("tob_revenue_oasdi", map_to="household", period=year)
        baseline_tob_total = baseline_sim.calculate("tob_revenue_total", map_to="household", period=year)
        tob_time = time.time() - tob_start
        print(f"      - TOB revenue variables calculated: {tob_time:.1f}s")

        print(f"      DIAGNOSTIC: About to sum baseline values...")
        baseline_revenue = float(baseline_income_tax.sum())
        baseline_tob_medicare_revenue = float(baseline_tob_medicare.sum())
        baseline_tob_oasdi_revenue = float(baseline_tob_oasdi.sum())
        baseline_tob_total_revenue = float(baseline_tob_total.sum())
        baseline_time = time.time() - baseline_start
        print(f"      ✓ Baseline calculated: ${baseline_revenue/1e9:.2f}B (total: {baseline_time:.1f}s)")
        print(f"        - TOB Medicare HI: ${baseline_tob_medicare_revenue/1e9:.2f}B")
        print(f"        - TOB OASDI: ${baseline_tob_oasdi_revenue/1e9:.2f}B")
        print(f"        - TOB Total: ${baseline_tob_total_revenue/1e9:.2f}B")

        # Clean up baseline objects immediately after extracting the value
        print(f"      DIAGNOSTIC: Cleaning up baseline objects...")
        del baseline_sim
        del baseline_income_tax
        del baseline_tob_medicare
        del baseline_tob_oasdi
        del baseline_tob_total
        gc.collect()
        print(f"      ✓ Baseline objects cleaned up")
    except Exception as e:
        print(f"      ✗ BASELINE CALCULATION FAILED: {e}")
        import traceback
        print("      DIAGNOSTIC: Full traceback:")
        traceback.print_exc()
        sys.exit(1)
    print()

    # Step 3: Run ALL reforms for this year (save each result incrementally)
    results = []
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # If only one reform, include reform name in filename (for parallelized jobs)
    # If multiple reforms, use year-based filename (for year-based jobs)
    if len(reform_ids) == 1:
        csv_path = f"results/{job_id}/{year}_{reform_ids[0]}_{scoring_type}_results.csv"
    else:
        csv_path = f"results/{job_id}/{year}_{scoring_type}_results.csv"

    for i, reform_id in enumerate(reform_ids, start=1):
        print(f"\n[{2+i}/{3+len(reform_ids)}] Computing {reform_id} for {year}...")
        print(f"      DIAGNOSTIC: Starting reform {reform_id} at {time.strftime('%H:%M:%S')}")
        reform_start = time.time()

        try:
            # Get reform function
            print(f"      DIAGNOSTIC: Looking up reform function for '{reform_id}'...")
            reform_func = REFORM_FUNCTIONS.get(reform_id)
            if not reform_func:
                print(f"      ✗ Unknown reform: {reform_id}")
                continue

            # Create reform based on scoring type
            if scoring_type == 'static':
                print(f"      DIAGNOSTIC: Creating static reform...")
                reform = reform_func()
                print(f"      ✓ Static reform created")
            elif scoring_type == 'dynamic':
                print(f"      DIAGNOSTIC: Starting dynamic reform creation...")
                # Get the complete dynamic dict function (with CBO elasticities pre-merged)
                print(f"      DIAGNOSTIC: Looking up dynamic dict function for '{reform_id}'...")
                dynamic_dict_func = REFORM_DYNAMIC_DICT_FUNCTIONS.get(reform_id)
                if not dynamic_dict_func:
                    print(f"      ✗ No dynamic dict function for {reform_id}")
                    continue

                print(f"      DIAGNOSTIC: Found dynamic dict function: {dynamic_dict_func.__name__}")
                # Get the complete parameter dictionary
                print(f"      DIAGNOSTIC: Calling {dynamic_dict_func.__name__}()...")
                reform_params = dynamic_dict_func()
                print(f"      DIAGNOSTIC: Got reform parameters dictionary with {len(reform_params)} keys")

                # Create single reform from complete parameters
                print(f"      DIAGNOSTIC: Creating Reform.from_dict() with {len(reform_params)} parameters...")
                reform = Reform.from_dict(reform_params, country_id="us")
                print(f"      ✓ Dynamic reform with CBO elasticities (pre-merged)")
                print(f"      DIAGNOSTIC: Reform object created successfully")
            else:
                print(f"      ✗ Invalid scoring type: {scoring_type}")
                continue

            # Run simulation with detailed timing
            print(f"      Running PolicyEngine simulation...")
            print(f"      DIAGNOSTIC: About to create reform Microsimulation...")
            sim_start = time.time()

            create_start = time.time()
            print(f"      DIAGNOSTIC: Calling Microsimulation(reform=<reform>, dataset='{dataset_name}')...")
            reform_sim = Microsimulation(reform=reform, dataset=dataset_name)
            create_time = time.time() - create_start
            print(f"        - Microsimulation object created: {create_time:.1f}s")
            print(f"      DIAGNOSTIC: Reform Microsimulation created successfully")

            calc_start = time.time()
            print(f"      DIAGNOSTIC: About to calculate reform income_tax...")
            reform_income_tax = reform_sim.calculate("income_tax", map_to="household", period=year)
            calc_time = time.time() - calc_start
            print(f"        - Income tax calculated: {calc_time:.1f}s")
            print(f"      DIAGNOSTIC: Reform income_tax calculated successfully")

            # Calculate TOB revenue variables for reform
            print(f"      DIAGNOSTIC: About to calculate reform TOB revenue variables...")
            tob_start = time.time()
            reform_tob_medicare = reform_sim.calculate("tob_revenue_medicare_hi", map_to="household", period=year)
            reform_tob_oasdi = reform_sim.calculate("tob_revenue_oasdi", map_to="household", period=year)
            reform_tob_total = reform_sim.calculate("tob_revenue_total", map_to="household", period=year)
            tob_time = time.time() - tob_start
            print(f"        - TOB revenue variables calculated: {tob_time:.1f}s")

            # Calculate employer payroll revenue variables for Options 5 & 6
            employer_ss_revenue = 0.0
            employer_medicare_revenue = 0.0
            if reform_id in ['option5', 'option6']:
                print(f"      DIAGNOSTIC: Calculating employer payroll revenue variables...")
                emp_start = time.time()
                try:
                    emp_ss = reform_sim.calculate("employer_ss_tax_income_tax_revenue", map_to="household", period=year)
                    emp_medicare = reform_sim.calculate("employer_medicare_tax_income_tax_revenue", map_to="household", period=year)
                    employer_ss_revenue = float(emp_ss.sum())
                    employer_medicare_revenue = float(emp_medicare.sum())
                    emp_time = time.time() - emp_start
                    print(f"        - Employer payroll revenue variables calculated: {emp_time:.1f}s")
                    print(f"        - Employer SS tax revenue: ${employer_ss_revenue/1e9:.2f}B")
                    print(f"        - Employer Medicare tax revenue: ${employer_medicare_revenue/1e9:.2f}B")
                except Exception as emp_error:
                    print(f"        - Warning: Could not calculate employer payroll variables: {emp_error}")

            reform_revenue = float(reform_income_tax.sum())
            reform_tob_medicare_revenue = float(reform_tob_medicare.sum())
            reform_tob_oasdi_revenue = float(reform_tob_oasdi.sum())
            reform_tob_total_revenue = float(reform_tob_total.sum())
            sim_time = time.time() - sim_start

            # Calculate impacts
            impact = reform_revenue - baseline_revenue
            tob_medicare_impact = reform_tob_medicare_revenue - baseline_tob_medicare_revenue
            tob_oasdi_impact = reform_tob_oasdi_revenue - baseline_tob_oasdi_revenue
            tob_total_impact = reform_tob_total_revenue - baseline_tob_total_revenue

            # Calculate allocated gains/losses for Options 5 & 6
            oasdi_gain = 0.0
            hi_gain = 0.0
            oasdi_loss = 0.0
            hi_loss = 0.0
            oasdi_net = 0.0
            hi_net = 0.0

            if reform_id in ['option5', 'option6']:
                # Calculate losses (from TOB reduction/elimination)
                oasdi_loss = baseline_tob_oasdi_revenue - reform_tob_oasdi_revenue
                hi_loss = baseline_tob_medicare_revenue - reform_tob_medicare_revenue

                # Calculate gains based on allocation rules
                if reform_id == 'option5':
                    # Option 5: Use branching results directly
                    oasdi_gain = employer_ss_revenue
                    hi_gain = employer_medicare_revenue
                elif reform_id == 'option6':
                    # Option 6: Phased allocation based on 6.2pp threshold
                    # Phase-in rates (percentage of employer payroll taxed)
                    phase_in_rates = {
                        2026: 0.1307, 2027: 0.2614, 2028: 0.3922, 2029: 0.5229,
                        2030: 0.6536, 2031: 0.7843, 2032: 0.9150
                    }

                    if year >= 2033:
                        # Fully phased in (100%) - use Option 5 branching approach
                        oasdi_gain = employer_ss_revenue
                        hi_gain = employer_medicare_revenue
                    else:
                        # During phase-in: allocate based on 6.2pp threshold
                        rate = phase_in_rates.get(year, 1.0)
                        total_pp = rate * 7.65  # Total percentage points included

                        total_gain = employer_ss_revenue + employer_medicare_revenue

                        if total_pp <= 6.2:
                            # All to OASDI when rate ≤ 6.2pp
                            oasdi_gain = total_gain
                            hi_gain = 0.0
                        else:
                            # Split: 6.2/rate to OASDI, remainder to HI
                            oasdi_share = 6.2 / total_pp
                            oasdi_gain = total_gain * oasdi_share
                            hi_gain = total_gain * (1 - oasdi_share)

                        print(f"        - Option 6 phase-in: {rate*100:.1f}% = {total_pp:.2f}pp, OASDI share: {(6.2/total_pp if total_pp > 6.2 else 1.0)*100:.1f}%")

                # Calculate net impacts
                oasdi_net = oasdi_gain - oasdi_loss
                hi_net = hi_gain - hi_loss

                print(f"        - OASDI gain: ${oasdi_gain/1e9:+.2f}B, loss: ${oasdi_loss/1e9:.2f}B, net: ${oasdi_net/1e9:+.2f}B")
                print(f"        - HI gain: ${hi_gain/1e9:+.2f}B, loss: ${hi_loss/1e9:.2f}B, net: ${hi_net/1e9:+.2f}B")

            reform_time = time.time() - reform_start
            print(f"      ✓ Reform revenue: ${reform_revenue/1e9:.2f}B")
            print(f"      ✓ Impact: ${impact/1e9:+.2f}B ({reform_time:.1f}s total, {sim_time:.1f}s simulation)")
            print(f"        - TOB Medicare HI impact: ${tob_medicare_impact/1e9:+.2f}B")
            print(f"        - TOB OASDI impact: ${tob_oasdi_impact/1e9:+.2f}B")
            print(f"        - TOB Total impact: ${tob_total_impact/1e9:+.2f}B")

            # Store result (include baseline for reference)
            result = {
                'reform_name': reform_id,
                'year': year,
                'baseline_revenue': baseline_revenue,
                'reform_revenue': reform_revenue,
                'revenue_impact': impact,
                'baseline_tob_medicare_hi': baseline_tob_medicare_revenue,
                'reform_tob_medicare_hi': reform_tob_medicare_revenue,
                'tob_medicare_hi_impact': tob_medicare_impact,
                'baseline_tob_oasdi': baseline_tob_oasdi_revenue,
                'reform_tob_oasdi': reform_tob_oasdi_revenue,
                'tob_oasdi_impact': tob_oasdi_impact,
                'baseline_tob_total': baseline_tob_total_revenue,
                'reform_tob_total': reform_tob_total_revenue,
                'tob_total_impact': tob_total_impact,
                'scoring_type': scoring_type,
                # New columns for Options 5 & 6 revenue allocation
                'employer_ss_tax_revenue': employer_ss_revenue,
                'employer_medicare_tax_revenue': employer_medicare_revenue,
                'oasdi_gain': oasdi_gain,
                'hi_gain': hi_gain,
                'oasdi_loss': oasdi_loss,
                'hi_loss': hi_loss,
                'oasdi_net_impact': oasdi_net,
                'hi_net_impact': hi_net
            }
            results.append(result)

            # CRITICAL: Clean up reform objects immediately to prevent memory accumulation
            del reform_sim
            del reform_income_tax
            del reform_tob_medicare
            del reform_tob_oasdi
            del reform_tob_total
            del reform
            gc.collect()
            print(f"      ✓ Memory cleaned up")

            # Save incrementally to Cloud Storage (only for multi-reform jobs)
            if len(reform_ids) > 1:
                try:
                    df = pd.DataFrame(results)
                    blob = bucket.blob(csv_path)
                    blob.upload_from_string(df.to_csv(index=False), content_type='text/csv')
                    print(f"      ✓ Incremental save to gs://{bucket_name}/{csv_path} ({len(results)}/{len(reform_ids)} reforms)")
                except Exception as save_error:
                    print(f"      ⚠ Warning: Failed to save intermediate results: {save_error}")
                    # Don't fail the whole job if intermediate save fails
                    pass
            else:
                print(f"      (Skipping incremental save - single reform job)")

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
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
