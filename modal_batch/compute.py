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

import modal
from pathlib import Path

# Get the project root (parent of modal_batch/)
PROJECT_ROOT = Path(__file__).parent.parent

# Create the Modal app
app = modal.App("crfb-ss-analysis")

# Define the image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "policyengine-us==1.98.1",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
    )
)

# Mount the src directory so we can import reforms.py
src_mount = modal.Mount.from_local_dir(
    PROJECT_ROOT / "src",
    remote_path="/app/src",
)


@app.function(
    image=image,
    mounts=[src_mount],
    cpu=4,
    memory=32768,  # 32GB
    timeout=3600,  # 1 hour max
)
def compute_year(
    year: int,
    reform_ids: list[str],
    scoring_type: str = "static",
) -> list[dict]:
    """
    Compute all specified reforms for a single year.

    Mirrors the GCP batch/compute_year.py logic:
    - Download dataset ONCE per year
    - Calculate baseline ONCE per year
    - Run ALL specified reforms for that year

    Args:
        year: Year to compute (e.g., 2026)
        reform_ids: List of reform IDs (e.g., ['option9', 'option10'])
        scoring_type: 'static' or 'dynamic'

    Returns:
        List of result dictionaries, one per reform
    """
    import sys
    import gc
    import time
    import warnings
    warnings.filterwarnings('ignore')

    # Add src to path for imports (same as GCP batch)
    sys.path.insert(0, '/app/src')

    from policyengine_us import Microsimulation
    from policyengine_core.reforms import Reform

    # Import reform functions from src/reforms.py (shared with GCP batch)
    from reforms import (
        get_option1_reform, get_option2_reform, get_option3_reform,
        get_option4_reform, get_option5_reform, get_option6_reform,
        get_option7_reform, get_option8_reform, get_option9_reform,
        get_option10_reform, get_option11_reform,
        get_option1_dynamic_dict, get_option2_dynamic_dict, get_option3_dynamic_dict,
        get_option4_dynamic_dict, get_option5_dynamic_dict, get_option6_dynamic_dict,
        get_option7_dynamic_dict, get_option8_dynamic_dict, get_option9_dynamic_dict,
        get_option10_dynamic_dict, get_option11_dynamic_dict,
    )

    # Reform functions for static scoring (same as GCP batch)
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

    print(f"\n{'='*60}")
    print(f"MODAL WORKER: Year {year} ({scoring_type.upper()} scoring)")
    print(f"Reforms: {', '.join(reform_ids)}")
    print(f"{'='*60}\n")

    # Step 1: Dataset reference (same as GCP batch)
    dataset_name = f"hf://policyengine/test/no-h6/{year}.h5"
    print(f"[1] Dataset: {dataset_name}")

    # Step 2: Calculate baseline ONCE (same logic as GCP batch)
    print(f"[2] Creating baseline simulation...")
    baseline_start = time.time()

    baseline_sim = Microsimulation(dataset=dataset_name)
    baseline_income_tax = baseline_sim.calculate("income_tax", map_to="household", period=year)
    baseline_tob_medicare = baseline_sim.calculate("tob_revenue_medicare_hi", map_to="household", period=year)
    baseline_tob_oasdi = baseline_sim.calculate("tob_revenue_oasdi", map_to="household", period=year)
    baseline_tob_total = baseline_sim.calculate("tob_revenue_total", map_to="household", period=year)

    baseline_revenue = float(baseline_income_tax.sum())
    baseline_tob_medicare_revenue = float(baseline_tob_medicare.sum())
    baseline_tob_oasdi_revenue = float(baseline_tob_oasdi.sum())
    baseline_tob_total_revenue = float(baseline_tob_total.sum())

    print(f"    Baseline: ${baseline_revenue/1e9:.2f}B ({time.time()-baseline_start:.1f}s)")
    print(f"    TOB - OASDI: ${baseline_tob_oasdi_revenue/1e9:.2f}B, Medicare HI: ${baseline_tob_medicare_revenue/1e9:.2f}B")

    # Clean up baseline objects
    del baseline_sim, baseline_income_tax, baseline_tob_medicare, baseline_tob_oasdi, baseline_tob_total
    gc.collect()

    # Step 3: Run reforms (same logic as GCP batch)
    results = []

    for i, reform_id in enumerate(reform_ids, start=1):
        print(f"\n[{2+i}] Computing {reform_id}...")
        reform_start = time.time()

        try:
            # Create reform based on scoring type (same as GCP batch)
            if scoring_type == 'static':
                reform_func = REFORM_FUNCTIONS.get(reform_id)
                if not reform_func:
                    print(f"    Unknown reform: {reform_id}")
                    continue
                reform = reform_func()
            else:  # dynamic
                dynamic_dict_func = REFORM_DYNAMIC_DICT_FUNCTIONS.get(reform_id)
                if not dynamic_dict_func:
                    print(f"    No dynamic dict for: {reform_id}")
                    continue
                reform_params = dynamic_dict_func()
                reform = Reform.from_dict(reform_params, country_id="us")

            # Run simulation
            reform_sim = Microsimulation(reform=reform, dataset=dataset_name)
            reform_income_tax = reform_sim.calculate("income_tax", map_to="household", period=year)
            reform_tob_medicare = reform_sim.calculate("tob_revenue_medicare_hi", map_to="household", period=year)
            reform_tob_oasdi = reform_sim.calculate("tob_revenue_oasdi", map_to="household", period=year)
            reform_tob_total = reform_sim.calculate("tob_revenue_total", map_to="household", period=year)

            reform_revenue = float(reform_income_tax.sum())
            reform_tob_medicare_revenue = float(reform_tob_medicare.sum())
            reform_tob_oasdi_revenue = float(reform_tob_oasdi.sum())
            reform_tob_total_revenue = float(reform_tob_total.sum())

            # Calculate impacts
            impact = reform_revenue - baseline_revenue
            tob_medicare_impact = reform_tob_medicare_revenue - baseline_tob_medicare_revenue
            tob_oasdi_impact = reform_tob_oasdi_revenue - baseline_tob_oasdi_revenue
            tob_total_impact = reform_tob_total_revenue - baseline_tob_total_revenue

            # Handle Options 5 & 6 employer payroll tax (same as GCP batch)
            employer_ss_revenue = 0.0
            employer_medicare_revenue = 0.0
            oasdi_gain = 0.0
            hi_gain = 0.0
            oasdi_loss = 0.0
            hi_loss = 0.0
            oasdi_net = tob_oasdi_impact
            hi_net = tob_medicare_impact

            if reform_id in ['option5', 'option6']:
                try:
                    emp_ss = reform_sim.calculate("employer_ss_tax_income_tax_revenue", map_to="household", period=year)
                    emp_medicare = reform_sim.calculate("employer_medicare_tax_income_tax_revenue", map_to="household", period=year)
                    employer_ss_revenue = float(emp_ss.sum())
                    employer_medicare_revenue = float(emp_medicare.sum())

                    # Calculate losses (from TOB reduction/elimination)
                    oasdi_loss = baseline_tob_oasdi_revenue - reform_tob_oasdi_revenue
                    hi_loss = baseline_tob_medicare_revenue - reform_tob_medicare_revenue

                    # Calculate gains based on allocation rules (same as GCP batch)
                    if reform_id == 'option5':
                        oasdi_gain = employer_ss_revenue
                        hi_gain = employer_medicare_revenue
                    elif reform_id == 'option6':
                        phase_in_rates = {
                            2026: 0.1307, 2027: 0.2614, 2028: 0.3922, 2029: 0.5229,
                            2030: 0.6536, 2031: 0.7843, 2032: 0.9150
                        }
                        if year >= 2033:
                            oasdi_gain = employer_ss_revenue
                            hi_gain = employer_medicare_revenue
                        else:
                            rate = phase_in_rates.get(year, 1.0)
                            total_pp = rate * 7.65
                            total_gain = employer_ss_revenue + employer_medicare_revenue
                            if total_pp <= 6.2:
                                oasdi_gain = total_gain
                                hi_gain = 0.0
                            else:
                                oasdi_share = 6.2 / total_pp
                                oasdi_gain = total_gain * oasdi_share
                                hi_gain = total_gain * (1 - oasdi_share)

                    oasdi_net = oasdi_gain - oasdi_loss
                    hi_net = hi_gain - hi_loss

                except Exception as e:
                    print(f"    Warning: employer payroll calc failed: {e}")

            reform_time = time.time() - reform_start
            print(f"    Impact: ${impact/1e9:+.2f}B ({reform_time:.1f}s)")
            print(f"    OASDI: ${tob_oasdi_impact/1e9:+.2f}B, Medicare HI: ${tob_medicare_impact/1e9:+.2f}B")

            # Store result (same columns as GCP batch)
            results.append({
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
                'employer_ss_tax_revenue': employer_ss_revenue,
                'employer_medicare_tax_revenue': employer_medicare_revenue,
                'oasdi_gain': oasdi_gain,
                'hi_gain': hi_gain,
                'oasdi_loss': oasdi_loss,
                'hi_loss': hi_loss,
                'oasdi_net_impact': oasdi_net,
                'hi_net_impact': hi_net,
            })

            # Clean up
            del reform_sim, reform_income_tax, reform_tob_medicare, reform_tob_oasdi, reform_tob_total, reform
            gc.collect()

        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"COMPLETE: {len(results)} reforms for year {year}")
    print(f"{'='*60}\n")

    return results


@app.local_entrypoint()
def test_single(reform: str = "option9", year: int = 2030, scoring: str = "static"):
    """Test a single reform/year combination."""
    print(f"\nTesting {reform} for {year} ({scoring})...")
    results = compute_year.remote(year, [reform], scoring)

    for r in results:
        print(f"\n{r['reform_name']} ({r['year']}):")
        print(f"  Revenue impact: ${r['revenue_impact']/1e9:+.2f}B")
        print(f"  OASDI impact: ${r['tob_oasdi_impact']/1e9:+.2f}B")
        print(f"  Medicare HI impact: ${r['tob_medicare_hi_impact']/1e9:+.2f}B")


@app.local_entrypoint()
def sniff_test(reforms: str = "option9,option10,option11", scoring: str = "static"):
    """Quick sniff test: run 3 sample years (2030, 2050, 2080) for specified reforms."""
    reform_list = [r.strip() for r in reforms.split(",")]
    test_years = [2030, 2050, 2080]

    print(f"\nSniff test: {reform_list} for years {test_years}")
    print("=" * 60)

    args = [(year, reform_list, scoring) for year in test_years]

    all_results = []
    for result_batch in compute_year.starmap(args):
        all_results.extend(result_batch)

    # Display results
    print("\n" + "=" * 60)
    print("SNIFF TEST RESULTS")
    print("=" * 60)

    for reform_id in reform_list:
        print(f"\n{reform_id}:")
        for year in test_years:
            result = next((r for r in all_results if r['reform_name'] == reform_id and r['year'] == year), None)
            if result:
                print(f"  {year}: ${result['revenue_impact']/1e9:+.2f}B (OASDI: ${result['tob_oasdi_impact']/1e9:+.2f}B)")


@app.local_entrypoint()
def run_reforms(
    reforms: str = "option9,option10,option11",
    scoring: str = "dynamic",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
):
    """
    Run multiple reforms across all years in parallel.

    Args:
        reforms: Comma-separated reform IDs
        scoring: 'static' or 'dynamic'
        years: Year range like '2026-2100' or comma-separated '2026,2030,2050'
        output: Output CSV path
    """
    import pandas as pd
    from pathlib import Path

    reform_list = [r.strip() for r in reforms.split(",")]

    # Parse years
    if "-" in years:
        start, end = years.split("-")
        year_list = list(range(int(start), int(end) + 1))
    else:
        year_list = [int(y.strip()) for y in years.split(",")]

    print(f"\nRunning {len(reform_list)} reforms x {len(year_list)} years")
    print(f"= {len(year_list)} parallel tasks (one per year)")
    print(f"Reforms: {reform_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    print()

    # Prepare arguments - one task per year (each year computes all reforms)
    args = [(year, reform_list, scoring) for year in year_list]

    # Run in parallel
    all_results = []
    for result_batch in compute_year.starmap(args):
        all_results.extend(result_batch)
        completed_years = len(all_results) // len(reform_list)
        print(f"  Completed: {completed_years}/{len(year_list)} years...")

    # Save results
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(all_results)
    df.to_csv(output, index=False)
    print(f"\nSaved {len(df)} results to {output}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY (75-year totals)")
    print("=" * 60)
    for reform_id in reform_list:
        reform_df = df[df['reform_name'] == reform_id]
        total_impact = reform_df['revenue_impact'].sum() / 1e9
        oasdi_impact = reform_df['tob_oasdi_impact'].sum() / 1e9
        hi_impact = reform_df['tob_medicare_hi_impact'].sum() / 1e9
        print(f"{reform_id}: ${total_impact:+,.1f}B total (OASDI: ${oasdi_impact:+,.1f}B, HI: ${hi_impact:+,.1f}B)")
