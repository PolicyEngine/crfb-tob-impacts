"""
Run Option 12 standalone (without Option 13 baseline).
Compares employer payroll tax reform to current law.
"""
import os
import sys
import modal
import pandas as pd
import numpy as np

app = modal.App("option12-standalone")

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
def compute_option12_standalone(year: int) -> dict:
    """Compute Option 12 standalone vs current law baseline."""
    from policyengine_us import Microsimulation
    from policyengine_core.reforms import Reform

    sys.path.insert(0, '/app/src')
    from reforms import get_option12_dict

    print(f"\n{'='*60}")
    print(f"OPTION 12 STANDALONE: {year}")
    print(f"{'='*60}")

    dataset = f"hf://policyengine/test/no-h6/{year}.h5"

    # Get Option 12 reform dict
    option12_dict = get_option12_dict()

    # =========================================================================
    # CURRENT LAW BASELINE
    # =========================================================================
    print("\nRunning current law baseline simulation...")
    baseline_sim = Microsimulation(dataset=dataset, start_instant=f"{year}-01-01")

    baseline_income_tax = baseline_sim.calculate("income_tax", year).sum()
    baseline_tob_oasdi = baseline_sim.calculate("tob_revenue_oasdi", year).sum()
    baseline_tob_hi = baseline_sim.calculate("tob_revenue_medicare_hi", year).sum()
    baseline_ss_benefits = baseline_sim.calculate("social_security", year).sum()

    print(f"Baseline: Income tax ${baseline_income_tax/1e9:.1f}B, SS benefits ${baseline_ss_benefits/1e9:.1f}B")

    # =========================================================================
    # OPTION 12: Employer payroll tax reform
    # =========================================================================
    print(f"\nRunning Option 12 reform simulation...")
    option12_reform = Reform.from_dict(option12_dict, country_id="us")
    reform_sim = Microsimulation(reform=option12_reform, dataset=dataset, start_instant=f"{year}-01-01")

    reform_income_tax = reform_sim.calculate("income_tax", year).sum()
    reform_tob_oasdi = reform_sim.calculate("tob_revenue_oasdi", year).sum()
    reform_tob_hi = reform_sim.calculate("tob_revenue_medicare_hi", year).sum()
    reform_ss_benefits = reform_sim.calculate("social_security", year).sum()

    # Employer payroll tax revenue (goes to trust funds)
    employer_ss_revenue = reform_sim.calculate("employer_ss_tax_income_tax_revenue", map_to="household", period=year).sum()
    employer_hi_revenue = reform_sim.calculate("employer_medicare_tax_income_tax_revenue", map_to="household", period=year).sum()

    # Calculate impacts
    income_tax_impact = reform_income_tax - baseline_income_tax
    oasdi_gain = float(employer_ss_revenue)
    hi_gain = float(employer_hi_revenue)
    oasdi_loss = float(baseline_tob_oasdi - reform_tob_oasdi)
    hi_loss = float(baseline_tob_hi - reform_tob_hi)
    oasdi_net = oasdi_gain - oasdi_loss
    hi_net = hi_gain - hi_loss

    print(f"\nOption 12 Standalone Results (vs Current Law):")
    print(f"  Income tax impact: ${income_tax_impact/1e9:+.1f}B")
    print(f"  OASDI net: ${oasdi_net/1e9:+.1f}B (gain: ${oasdi_gain/1e9:.1f}B, loss: ${oasdi_loss/1e9:.1f}B)")
    print(f"  HI net: ${hi_net/1e9:+.1f}B (gain: ${hi_gain/1e9:.1f}B, loss: ${hi_loss/1e9:.1f}B)")

    result = {
        "year": year,
        "baseline_income_tax": float(baseline_income_tax),
        "baseline_tob_oasdi": float(baseline_tob_oasdi),
        "baseline_tob_hi": float(baseline_tob_hi),
        "baseline_ss_benefits": float(baseline_ss_benefits),
        "reform_income_tax": float(reform_income_tax),
        "reform_tob_oasdi": float(reform_tob_oasdi),
        "reform_tob_hi": float(reform_tob_hi),
        "reform_ss_benefits": float(reform_ss_benefits),
        "income_tax_impact": float(income_tax_impact),
        "employer_ss_tax_revenue": float(employer_ss_revenue),
        "employer_hi_tax_revenue": float(employer_hi_revenue),
        "oasdi_gain": oasdi_gain,
        "hi_gain": hi_gain,
        "oasdi_loss": oasdi_loss,
        "hi_loss": hi_loss,
        "oasdi_net_impact": oasdi_net,
        "hi_net_impact": hi_net,
    }

    os.makedirs("/results/option12_standalone", exist_ok=True)
    pd.DataFrame([result]).to_csv(f"/results/option12_standalone/{year}_static_results.csv", index=False)

    results_volume.commit()
    return result


@app.local_entrypoint()
def main(years: str = "2040,2055,2070,2085,2095"):
    """Run Option 12 standalone for specified years."""
    year_list = [int(y.strip()) for y in years.split(",") if y.strip()]

    print(f"Running Option 12 standalone for years: {year_list}")

    for result in compute_option12_standalone.map(year_list):
        print(f"\n=== Year {result['year']} - Option 12 Standalone ===")
        print(f"  Income tax: ${result['income_tax_impact']/1e9:+.1f}B")
        print(f"  OASDI net: ${result['oasdi_net_impact']/1e9:+.1f}B")
        print(f"  HI net: ${result['hi_net_impact']/1e9:+.1f}B")
