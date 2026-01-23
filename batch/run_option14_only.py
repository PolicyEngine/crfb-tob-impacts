"""
Run Option 14 (Extended Roth) using pre-computed Option 13 parameters.
Loads benefit_multiplier and rate increases from saved Option 13 results.
"""
import os
import sys
import modal
import pandas as pd
import numpy as np

app = modal.App("option14-only")

results_volume = modal.Volume.from_name("crfb-results", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("pandas", "numpy", "h5py", "tables")
    .add_local_dir("data", "/app/data", copy=True)
    .add_local_dir("src", "/app/src", copy=True)
    .add_local_dir("/Users/pavelmakarchuk/policyengine-us", "/app/policyengine-us", copy=True)
    .run_commands("pip install -e /app/policyengine-us")
)


@app.function(
    image=image,
    volumes={"/results": results_volume},
    timeout=7200,  # 2 hours
    memory=32000,
)
def compute_option14_year(year: int) -> dict:
    """Compute Option 14 (Stacked) and Option 12 standalone for a single year.

    Loads Option 13 parameters from saved results.
    """
    from policyengine_us import Microsimulation
    from policyengine_core.reforms import Reform

    sys.path.insert(0, '/app/src')
    from reforms import get_option12_dict

    print(f"\n{'='*60}")
    print(f"OPTION 14 (using saved Option 13 params): {year}")
    print(f"{'='*60}")

    # Load Option 13 parameters
    opt13_path = f"/results/option13/{year}_static_results.csv"
    if not os.path.exists(opt13_path):
        return {"year": year, "error": f"Option 13 results not found for {year}"}

    opt13_df = pd.read_csv(opt13_path)
    opt13 = opt13_df.iloc[0]

    benefit_multiplier = opt13['benefit_multiplier']
    new_employee_ss_rate = opt13['new_employee_ss_rate']
    new_employer_ss_rate = opt13['new_employer_ss_rate']
    new_employee_hi_rate = opt13['new_employee_hi_rate']
    new_employer_hi_rate = opt13['new_employer_hi_rate']

    print(f"Loaded Option 13 params:")
    print(f"  Benefit multiplier: {benefit_multiplier:.4f}")
    print(f"  SS rate: {new_employee_ss_rate*100:.2f}%")
    print(f"  HI rate: {new_employee_hi_rate*100:.2f}%")

    dataset = f"hf://policyengine/test/no-h6/{year}.h5"

    # Get Option 12 reform dict
    option12_dict = get_option12_dict()

    # Build Option 13 (balanced fix) reform dict for rates
    option13_reform_dict = {
        "gov.irs.payroll.social_security.rate.employee": {
            "2020-01-01.2100-12-31": new_employee_ss_rate
        },
        "gov.irs.payroll.social_security.rate.employer": {
            "2020-01-01.2100-12-31": new_employer_ss_rate
        },
        "gov.irs.payroll.medicare.rate.employee": {
            "2020-01-01.2100-12-31": new_employee_hi_rate
        },
        "gov.irs.payroll.medicare.rate.employer": {
            "2020-01-01.2100-12-31": new_employer_hi_rate
        },
    }

    # =========================================================================
    # BASELINE: Option 13 (balanced fix) - for comparison
    # =========================================================================
    print("\nRunning Option 13 baseline simulation...")
    baseline_reform = Reform.from_dict(option13_reform_dict, country_id="us")
    baseline_sim = Microsimulation(reform=baseline_reform, dataset=dataset, start_instant=f"{year}-01-01")

    # Apply benefit cuts
    original_ss = baseline_sim.calculate("social_security", year)
    reduced_ss_values = np.array(original_ss.values) * benefit_multiplier
    baseline_sim.set_input("social_security", year, reduced_ss_values)

    baseline_income_tax = baseline_sim.calculate("income_tax", year).sum()
    baseline_tob_oasdi = baseline_sim.calculate("tob_revenue_oasdi", year).sum()
    baseline_tob_hi = baseline_sim.calculate("tob_revenue_medicare_hi", year).sum()
    baseline_ss_benefits = baseline_sim.calculate("social_security", year).sum()

    print(f"Baseline (Option 13): Income tax ${baseline_income_tax/1e9:.1f}B, SS benefits ${baseline_ss_benefits/1e9:.1f}B")

    results = {"year": year}

    # =========================================================================
    # OPTION 14 STACKED: Option 13 + Option 12
    # =========================================================================
    print(f"\n{'='*60}")
    print(f"OPTION 14 STACKED (Option 13 + Option 12): {year}")
    print(f"{'='*60}")

    # Combine Option 13 rates + Option 12 reforms
    stacked_reform_dict = {**option13_reform_dict}
    stacked_reform_dict.update(option12_dict)

    stacked_reform = Reform.from_dict(stacked_reform_dict, country_id="us")
    print("Running stacked simulation...")
    stacked_sim = Microsimulation(reform=stacked_reform, dataset=dataset, start_instant=f"{year}-01-01")

    # Apply same benefit cuts
    stacked_sim.set_input("social_security", year, reduced_ss_values)

    stacked_income_tax = stacked_sim.calculate("income_tax", year).sum()
    stacked_tob_oasdi = stacked_sim.calculate("tob_revenue_oasdi", year).sum()
    stacked_tob_hi = stacked_sim.calculate("tob_revenue_medicare_hi", year).sum()

    # Option 12 specific: employer payroll tax revenue
    stacked_employer_ss_revenue = stacked_sim.calculate("employer_ss_tax_income_tax_revenue", map_to="household", period=year).sum()
    stacked_employer_hi_revenue = stacked_sim.calculate("employer_medicare_tax_income_tax_revenue", map_to="household", period=year).sum()

    # Impacts vs Option 13 baseline
    stacked_income_tax_impact = stacked_income_tax - baseline_income_tax
    stacked_oasdi_gain = float(stacked_employer_ss_revenue)
    stacked_hi_gain = float(stacked_employer_hi_revenue)
    stacked_oasdi_loss = float(baseline_tob_oasdi - stacked_tob_oasdi)
    stacked_hi_loss = float(baseline_tob_hi - stacked_tob_hi)
    stacked_oasdi_net = stacked_oasdi_gain - stacked_oasdi_loss
    stacked_hi_net = stacked_hi_gain - stacked_hi_loss

    print(f"\nStacked Results (vs Option 13 baseline):")
    print(f"  Income tax impact: ${stacked_income_tax_impact/1e9:+.1f}B")
    print(f"  OASDI net: ${stacked_oasdi_net/1e9:+.1f}B (gain: ${stacked_oasdi_gain/1e9:.1f}B, loss: ${stacked_oasdi_loss/1e9:.1f}B)")
    print(f"  HI net: ${stacked_hi_net/1e9:+.1f}B (gain: ${stacked_hi_gain/1e9:.1f}B, loss: ${stacked_hi_loss/1e9:.1f}B)")

    stacked_result = {
        "year": year,
        "baseline_income_tax": float(baseline_income_tax),
        "baseline_tob_oasdi": float(baseline_tob_oasdi),
        "baseline_tob_hi": float(baseline_tob_hi),
        "reform_income_tax": float(stacked_income_tax),
        "reform_tob_oasdi": float(stacked_tob_oasdi),
        "reform_tob_hi": float(stacked_tob_hi),
        "income_tax_impact": float(stacked_income_tax_impact),
        "employer_ss_tax_revenue": float(stacked_employer_ss_revenue),
        "employer_hi_tax_revenue": float(stacked_employer_hi_revenue),
        "oasdi_gain": stacked_oasdi_gain,
        "hi_gain": stacked_hi_gain,
        "oasdi_loss": stacked_oasdi_loss,
        "hi_loss": stacked_hi_loss,
        "oasdi_net_impact": stacked_oasdi_net,
        "hi_net_impact": stacked_hi_net,
    }

    os.makedirs("/results/option14_stacked", exist_ok=True)
    pd.DataFrame([stacked_result]).to_csv(f"/results/option14_stacked/{year}_static_results.csv", index=False)
    results['option14_stacked'] = stacked_result

    # =========================================================================
    # OPTION 12 STANDALONE: Option 12 only vs Option 13 baseline
    # =========================================================================
    print(f"\n{'='*60}")
    print(f"OPTION 12 STANDALONE (vs Option 13 baseline): {year}")
    print(f"{'='*60}")

    # Option 12 only - no rate increases, no benefit cuts
    option12_reform = Reform.from_dict(option12_dict, country_id="us")
    print("Running Option 12 standalone simulation...")
    option12_sim = Microsimulation(reform=option12_reform, dataset=dataset, start_instant=f"{year}-01-01")

    # NO benefit cuts - uses original SS benefits

    option12_income_tax = option12_sim.calculate("income_tax", year).sum()
    option12_tob_oasdi = option12_sim.calculate("tob_revenue_oasdi", year).sum()
    option12_tob_hi = option12_sim.calculate("tob_revenue_medicare_hi", year).sum()
    option12_ss_benefits = option12_sim.calculate("social_security", year).sum()

    option12_employer_ss_revenue = option12_sim.calculate("employer_ss_tax_income_tax_revenue", map_to="household", period=year).sum()
    option12_employer_hi_revenue = option12_sim.calculate("employer_medicare_tax_income_tax_revenue", map_to="household", period=year).sum()

    # Impacts vs Option 13 baseline
    option12_income_tax_impact = option12_income_tax - baseline_income_tax
    option12_oasdi_gain = float(option12_employer_ss_revenue)
    option12_hi_gain = float(option12_employer_hi_revenue)
    option12_oasdi_loss = float(baseline_tob_oasdi - option12_tob_oasdi)
    option12_hi_loss = float(baseline_tob_hi - option12_tob_hi)
    option12_oasdi_net = option12_oasdi_gain - option12_oasdi_loss
    option12_hi_net = option12_hi_gain - option12_hi_loss

    print(f"\nOption 12 Standalone Results (vs Option 13 baseline):")
    print(f"  Income tax impact: ${option12_income_tax_impact/1e9:+.1f}B")
    print(f"  OASDI net: ${option12_oasdi_net/1e9:+.1f}B (gain: ${option12_oasdi_gain/1e9:.1f}B, loss: ${option12_oasdi_loss/1e9:.1f}B)")
    print(f"  HI net: ${option12_hi_net/1e9:+.1f}B (gain: ${option12_hi_gain/1e9:.1f}B, loss: ${option12_hi_loss/1e9:.1f}B)")

    option12_result = {
        "year": year,
        "baseline_income_tax": float(baseline_income_tax),
        "baseline_tob_oasdi": float(baseline_tob_oasdi),
        "baseline_tob_hi": float(baseline_tob_hi),
        "baseline_ss_benefits": float(baseline_ss_benefits),
        "reform_income_tax": float(option12_income_tax),
        "reform_tob_oasdi": float(option12_tob_oasdi),
        "reform_tob_hi": float(option12_tob_hi),
        "reform_ss_benefits": float(option12_ss_benefits),
        "income_tax_impact": float(option12_income_tax_impact),
        "employer_ss_tax_revenue": float(option12_employer_ss_revenue),
        "employer_hi_tax_revenue": float(option12_employer_hi_revenue),
        "oasdi_gain": option12_oasdi_gain,
        "hi_gain": option12_hi_gain,
        "oasdi_loss": option12_oasdi_loss,
        "hi_loss": option12_hi_loss,
        "oasdi_net_impact": option12_oasdi_net,
        "hi_net_impact": option12_hi_net,
    }

    os.makedirs("/results/option12_standalone", exist_ok=True)
    pd.DataFrame([option12_result]).to_csv(f"/results/option12_standalone/{year}_static_results.csv", index=False)
    results['option12_standalone'] = option12_result

    results_volume.commit()
    return results


@app.local_entrypoint()
def main(years: str = "2040,2055,2070,2085,2095"):
    """Run Option 14 for specified years using saved Option 13 parameters."""
    year_list = [int(y.strip()) for y in years.split(",") if y.strip()]

    print(f"Running Option 14 (Stacked + Standalone) for years: {year_list}")
    print("Using pre-computed Option 13 parameters from Modal volume")

    for result in compute_option14_year.map(year_list):
        if result.get('error'):
            print(f"\n=== Year {result['year']} - ERROR: {result['error']} ===")
            continue

        if result.get('option14_stacked'):
            opt = result['option14_stacked']
            print(f"\n=== Year {opt['year']} - Stacked (Option 13 + 12) ===")
            print(f"  Income tax: ${opt['income_tax_impact']/1e9:+.1f}B")
            print(f"  OASDI net: ${opt['oasdi_net_impact']/1e9:+.1f}B")
            print(f"  HI net: ${opt['hi_net_impact']/1e9:+.1f}B")

        if result.get('option12_standalone'):
            opt = result['option12_standalone']
            print(f"\n=== Year {opt['year']} - Option 12 Standalone ===")
            print(f"  Income tax: ${opt['income_tax_impact']/1e9:+.1f}B")
            print(f"  OASDI net: ${opt['oasdi_net_impact']/1e9:+.1f}B")
            print(f"  HI net: ${opt['hi_net_impact']/1e9:+.1f}B")
