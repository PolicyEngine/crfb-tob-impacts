#!/usr/bin/env python3
"""
Phase 2 Worker: Compute reform impact for a single reform-year-scoring combination.

This script calculates the revenue impact of a reform for one year, using either
static or dynamic scoring.

Usage:
    python compute_reform.py REFORM_ID YEAR SCORING_TYPE BUCKET_NAME JOB_ID

Arguments:
    REFORM_ID: Reform identifier (e.g., 'option1')
    YEAR: Year to compute (e.g., 2026)
    SCORING_TYPE: 'static' or 'dynamic'
    BUCKET_NAME: Cloud Storage bucket name
    JOB_ID: Unique job identifier for organizing results
"""

import sys
import os
import json
import warnings
warnings.filterwarnings('ignore')

# Add src to path for imports
sys.path.insert(0, '/app/src')

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
        "2024-01-01.2100-12-31": 0.22
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.9": {
        "2024-01-01.2100-12-31": 0.22
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.10": {
        "2024-01-01.2100-12-31": 0.22
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.secondary": {
        "2024-01-01.2100-12-31": 0.27
    },
}


def get_reform_dict(reform_func):
    """Extract parameter dictionary from reform function."""
    from reforms import (
        eliminate_ss_taxation, tax_85_percent_ss,
        extend_senior_deduction, add_ss_tax_credit, eliminate_senior_deduction,
        enable_employer_payroll_tax
    )

    reform_func_name = reform_func.__name__

    if reform_func_name == "get_option1_reform":
        return eliminate_ss_taxation()
    elif reform_func_name == "get_option2_reform":
        return tax_85_percent_ss()
    elif reform_func_name == "get_option3_reform":
        return {**tax_85_percent_ss(), **extend_senior_deduction()}
    elif reform_func_name == "get_option4_reform":
        return {**tax_85_percent_ss(), **add_ss_tax_credit(500), **eliminate_senior_deduction()}
    elif reform_func_name == "get_option5_reform":
        return {**eliminate_ss_taxation(), **enable_employer_payroll_tax(1.0)}
    elif reform_func_name == "get_option6_reform":
        # Option 6: Phased Roth-Style Swap
        reform_dict = {
            "gov.contrib.crfb.tax_employer_payroll_tax.in_effect": {
                "2026-01-01.2100-12-31": True
            },
            "gov.contrib.crfb.tax_employer_payroll_tax.percentage": {
                "2026": 0.1307,
                "2027": 0.2614,
                "2028": 0.3922,
                "2029": 0.5229,
                "2030": 0.6536,
                "2031": 0.7843,
                "2032": 0.9150,
                "2033-01-01.2100-12-31": 1.0
            }
        }

        # Phase down base rate parameters
        base_years = [2029, 2030, 2031, 2032, 2033, 2034, 2035, 2036, 2037]
        base_values = [0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]

        for param_name in ["benefit_cap", "excess"]:
            param_path = f"gov.irs.social_security.taxability.rate.base.{param_name}"
            reform_dict[param_path] = {}
            for year, value in zip(base_years, base_values):
                reform_dict[param_path][str(year)] = value
            reform_dict[param_path]["2038-01-01.2100-12-31"] = 0

        # Phase down additional rate parameters
        add_years = list(range(2029, 2045))
        add_values = [0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40,
                      0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]

        for param_name in ["benefit_cap", "bracket", "excess"]:
            param_path = f"gov.irs.social_security.taxability.rate.additional.{param_name}"
            reform_dict[param_path] = {}
            for year, value in zip(add_years, add_values):
                reform_dict[param_path][str(year)] = value
            reform_dict[param_path]["2045-01-01.2100-12-31"] = 0

        return reform_dict

    elif reform_func_name == "get_option7_reform":
        return eliminate_senior_deduction()
    else:
        raise ValueError(f"Unknown reform function: {reform_func_name}")


def compute_reform(reform_id, year, scoring_type, bucket_name, job_id):
    """Compute reform impact for a single reform-year-scoring combination."""
    print(f"=" * 80)
    print(f"REFORM CALCULATION: {reform_id} / {year} / {scoring_type}")
    print(f"=" * 80)

    try:
        # Import required modules
        print(f"[1/6] Importing modules...")
        from policyengine_us import Microsimulation
        from policyengine_core.reforms import Reform
        from reforms import REFORMS
        from google.cloud import storage

        # Get reform configuration
        print(f"[2/6] Loading reform configuration...")
        if reform_id not in REFORMS:
            raise ValueError(f"Unknown reform_id: {reform_id}")

        reform_config = REFORMS[reform_id]
        reform_name = reform_config['name']
        reform_func = reform_config['func']

        print(f"      Reform: {reform_name}")
        print(f"      Scoring: {scoring_type.upper()}")

        # Download baseline total from Phase 1
        print(f"[3/6] Downloading baseline from Phase 1...")
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        baseline_blob = bucket.blob(f"baselines/{year}.json")

        try:
            baseline_data = json.loads(baseline_blob.download_as_string())
            baseline_total = baseline_data['baseline_total']
            print(f"      ✓ Baseline: ${baseline_total:,.0f} (${baseline_total/1e9:.2f}B)")
        except Exception as e:
            raise RuntimeError(
                f"Failed to download baseline for year {year}. "
                f"Make sure Phase 1 (baselines) completed successfully. Error: {e}"
            )

        # Create reform (static or dynamic)
        print(f"[4/6] Creating reform...")
        reform_dict = get_reform_dict(reform_func)

        if scoring_type == 'dynamic':
            # Add CBO labor elasticities
            combined_dict = {**reform_dict, **CBO_LABOR_PARAMS}
            reform = Reform.from_dict(combined_dict, country_id="us")
            print(f"      ✓ Dynamic reform with CBO elasticities")
        elif scoring_type == 'static':
            reform = Reform.from_dict(reform_dict, country_id="us")
            print(f"      ✓ Static reform (no behavioral responses)")
        else:
            raise ValueError(f"Unknown scoring_type: {scoring_type}. Must be 'static' or 'dynamic'")

        # Calculate reform impact
        print(f"[5/6] Running PolicyEngine simulation...")
        print(f"      (Using {year} dataset)")
        reform_sim = Microsimulation(reform=reform)
        reform_income_tax = reform_sim.calculate(
            "income_tax",
            map_to="household",
            period=year
        )
        reform_total = float(reform_income_tax.sum())

        revenue_impact = reform_total - baseline_total

        print(f"      ✓ Reform total: ${reform_total:,.0f} (${reform_total/1e9:.2f}B)")
        print(f"      ✓ Impact: ${revenue_impact:,.0f} (${revenue_impact/1e9:.2f}B)")

        # Save result
        print(f"[6/6] Saving result to Cloud Storage...")
        result = {
            'reform_id': reform_id,
            'reform_name': reform_name,
            'year': year,
            'scoring_type': scoring_type,
            'baseline_total': baseline_total,
            'reform_total': reform_total,
            'revenue_impact': revenue_impact
        }

        result_blob = bucket.blob(f"results/{job_id}/{reform_id}_{year}_{scoring_type}.json")
        result_blob.upload_from_string(json.dumps(result, indent=2))

        print(f"      ✓ Saved to: gs://{bucket_name}/results/{job_id}/{reform_id}_{year}_{scoring_type}.json")
        print(f"\n{'=' * 80}")
        print(f"✓ SUCCESS: {reform_id} / {year} / {scoring_type}")
        print(f"{'=' * 80}\n")

        return result

    except Exception as e:
        print(f"\n{'=' * 80}")
        print(f"✗ ERROR: {reform_id} / {year} / {scoring_type} failed")
        print(f"{'=' * 80}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python compute_reform.py REFORM_ID YEAR SCORING_TYPE BUCKET_NAME JOB_ID")
        print("Example: python compute_reform.py option1 2026 dynamic crfb-ss-analysis-results job-abc123")
        sys.exit(1)

    reform_id = sys.argv[1]
    year = int(sys.argv[2])
    scoring_type = sys.argv[3]
    bucket_name = sys.argv[4]
    job_id = sys.argv[5]

    compute_reform(reform_id, year, scoring_type, bucket_name, job_id)
