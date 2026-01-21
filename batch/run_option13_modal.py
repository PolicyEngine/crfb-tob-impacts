#!/usr/bin/env python3
"""
Run Option 13 (Balanced Fix) and Option 14 (Option 12 vs Balanced Fix) on Modal.

Option 13: Gap-closing "traditional fix" baseline (50% benefit cuts + 50% rate increases)
           Does NOT include employer payroll tax reform - provides apples-to-apples comparison
Option 14: Option 12 (Extended Roth-Style Swap) vs the balanced fix baseline

Usage:
    modal run batch/run_option13_modal.py --years 2035,2036,2037
    modal run batch/run_option13_modal.py --years 2035 --option14-only  # Skip option13 if already done
"""

import modal
import pandas as pd
from pathlib import Path

# Get the project root (parent of batch/)
PROJECT_ROOT = Path(__file__).parent.parent

app = modal.App("option13-test")

# Create volume for results
results_volume = modal.Volume.from_name("crfb-results", create_if_missing=True)

# Path to local policyengine-us repo (contains TOB variables)
POLICYENGINE_US_PATH = Path("/Users/pavelmakarchuk/policyengine-us")

# Container image with local policyengine-us (includes TOB variables)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "pandas",
        "numpy",
        "h5py",
        "huggingface_hub",
    )
    # Copy local policyengine-us and install (copy=True allows run_commands after)
    .add_local_dir(POLICYENGINE_US_PATH, "/app/policyengine-us", copy=True)
    .run_commands("pip install -e /app/policyengine-us")
    # Copy data directory for HI expenditures CSV
    .add_local_dir(PROJECT_ROOT / "data", "/app/data")
    # Copy src directory for reforms.py (Option 12 dict)
    .add_local_dir(PROJECT_ROOT / "src", "/app/src")
)

# Two-stage approach for "traditional fix" (no employer tax reform):
# Stage 1: Apply benefit cuts only, measure remaining gaps
# Stage 2: Close remaining gaps with payroll rate increases

# HI data from Trustees 2025 (loaded inline to avoid file dependencies)
HI_DATA = None

def get_hi_data():
    """Load HI data from CSV or use cached version."""
    global HI_DATA
    if HI_DATA is not None:
        return HI_DATA

    import os
    # In Modal container, data is at /app/data/
    paths = ['/app/data/hi_expenditures_tr2025.csv', 'data/hi_expenditures_tr2025.csv']
    for path in paths:
        if os.path.exists(path):
            df = pd.read_csv(path)
            HI_DATA = {
                int(row['year']): {
                    'hi_taxable_payroll': row['hi_taxable_payroll'],
                    'hi_expenditures': row['hi_expenditures']
                }
                for _, row in df.iterrows()
            }
            print(f"Loaded HI data from {path}")
            return HI_DATA

    raise FileNotFoundError(f"HI expenditures CSV not found in: {paths}")


@app.function(
    image=image,
    timeout=7200,  # 2 hour timeout (increased for complex years)
    memory=32768,
    volumes={"/results": results_volume},
)
def compute_option13_and_14_year(year: int, skip_option13: bool = False, skip_option14: bool = False) -> dict:
    """Compute Option 13 (Balanced Fix) and/or Option 14 (Option 12 vs Balanced Fix) for a single year.

    Args:
        year: Year to compute
        skip_option13: If True, skip Option 13 save (still computes baseline for Option 14)
        skip_option14: If True, skip Option 14 computation

    Returns:
        Dict with 'option13' and/or 'option14' results (only keys for computed options)
    """
    import sys
    import numpy as np
    from policyengine_us import Microsimulation
    from policyengine_core.reforms import Reform

    # Add src to path for imports
    sys.path.insert(0, '/app/src')
    from reforms import get_option12_dict

    print(f"\n{'='*60}")
    print(f"OPTION 13 (BALANCED FIX): {year}")
    print(f"{'='*60}")

    hi_data = get_hi_data()
    if year not in hi_data:
        return {"year": year, "error": f"No HI data for year {year}"}

    hi_info = hi_data[year]
    medicare_expenditures = hi_info['hi_expenditures']

    dataset = f"hf://policyengine/test/no-h6/{year}.h5"

    # Run baseline
    print("Running baseline simulation...")
    baseline = Microsimulation(dataset=dataset)

    # SS components
    employee_ss_tax = baseline.calculate("employee_social_security_tax", year).sum()
    employer_ss_tax = baseline.calculate("employer_social_security_tax", year).sum()
    tob_oasdi = baseline.calculate("tob_revenue_oasdi", year).sum()

    ss_benefits_series = baseline.calculate("social_security", year)
    ss_benefits = ss_benefits_series.sum()
    ss_benefits_values = np.array(ss_benefits_series.values)

    # HI components
    employee_hi_tax = baseline.calculate("employee_medicare_tax", year).sum()
    employer_hi_tax = baseline.calculate("employer_medicare_tax", year).sum()
    additional_medicare_tax = baseline.calculate("additional_medicare_tax", year).sum()
    tob_hi = baseline.calculate("tob_revenue_medicare_hi", year).sum()

    # Baseline income tax
    baseline_income_tax = baseline.calculate("income_tax", year).sum()

    # Get current rates
    params = baseline.tax_benefit_system.parameters
    current_employee_ss_rate = float(params.gov.irs.payroll.social_security.rate.employee(f"{year}-01-01"))
    current_employer_ss_rate = float(params.gov.irs.payroll.social_security.rate.employer(f"{year}-01-01"))
    current_employee_hi_rate = float(params.gov.irs.payroll.medicare.rate.employee(f"{year}-01-01"))
    current_employer_hi_rate = float(params.gov.irs.payroll.medicare.rate.employer(f"{year}-01-01"))

    print(f"Baseline SS Benefits: ${ss_benefits / 1e9:.1f}B")
    print(f"Baseline Income Tax: ${baseline_income_tax / 1e9:.1f}B")

    # Calculate gaps
    ss_income = employee_ss_tax + employer_ss_tax + tob_oasdi
    ss_gap = ss_income - ss_benefits

    hi_income = employee_hi_tax + employer_hi_tax + additional_medicare_tax + tob_hi
    hi_gap = hi_income - medicare_expenditures

    ss_shortfall = abs(min(ss_gap, 0))
    hi_shortfall = abs(min(hi_gap, 0))

    print(f"SS Gap: ${ss_gap / 1e9:.1f}B, HI Gap: ${hi_gap / 1e9:.1f}B")

    # ==========================================================================
    # TWO-STAGE APPROACH: Simpler gap closing without TOB estimation
    # ==========================================================================
    # Stage 1: Apply 50% benefit cut, measure actual remaining gaps
    # Stage 2: Close remaining gaps with rate increases
    # ==========================================================================

    # Get taxable payroll directly from PolicyEngine variables
    # SS: capped at wage base, Medicare: no cap (all wages)
    oasdi_taxable_payroll = baseline.calculate("taxable_earnings_for_social_security", year).sum()
    hi_taxable_payroll = baseline.calculate("payroll_tax_gross_wages", year).sum()

    print(f"Taxable payroll: SS ${oasdi_taxable_payroll/1e12:.2f}T, HI ${hi_taxable_payroll/1e12:.2f}T")

    # ==========================================================================
    # STAGE 1: Apply benefit cuts only (no employer tax reform), measure remaining gaps
    # ==========================================================================
    print("\n=== STAGE 1: Measure gaps after benefit cuts ===")

    # Straight 50% benefit cut (no TOB inflation needed)
    benefit_cut = ss_shortfall * 0.5
    benefit_multiplier = 1 - (benefit_cut / ss_benefits)
    print(f"Benefit cut: ${benefit_cut/1e9:.1f}B ({(1-benefit_multiplier)*100:.1f}% cut)")

    # Stage 1: Just benefit cuts, no other reforms
    # Use baseline simulation with modified SS benefits
    stage1_sim = Microsimulation(dataset=dataset, start_instant=f"{year}-01-01")

    # Apply benefit cut
    reduced_ss_values = ss_benefits_values * benefit_multiplier
    stage1_sim.set_input("social_security", year, reduced_ss_values)

    # Calculate Stage 1 results
    stage1_ss_benefits = stage1_sim.calculate("social_security", year).sum()
    stage1_employee_ss = stage1_sim.calculate("employee_social_security_tax", year).sum()
    stage1_employer_ss = stage1_sim.calculate("employer_social_security_tax", year).sum()
    stage1_tob_oasdi = stage1_sim.calculate("tob_revenue_oasdi", year).sum()
    stage1_employee_hi = stage1_sim.calculate("employee_medicare_tax", year).sum()
    stage1_employer_hi = stage1_sim.calculate("employer_medicare_tax", year).sum()
    stage1_additional_medicare = stage1_sim.calculate("additional_medicare_tax", year).sum()
    stage1_tob_hi = stage1_sim.calculate("tob_revenue_medicare_hi", year).sum()

    # Calculate remaining gaps AFTER benefit cuts (no employer tax revenue)
    stage1_ss_income = stage1_employee_ss + stage1_employer_ss + stage1_tob_oasdi
    stage1_hi_income = stage1_employee_hi + stage1_employer_hi + stage1_additional_medicare + stage1_tob_hi

    stage1_ss_gap = stage1_ss_income - stage1_ss_benefits  # Trust fund gap (payroll taxes only)
    stage1_hi_gap = stage1_hi_income - medicare_expenditures

    # Remaining gaps = stage 1 gaps (no employer tax revenue to add)
    remaining_ss_gap = stage1_ss_gap
    remaining_hi_gap = stage1_hi_gap

    print(f"After benefit cuts:")
    print(f"  SS: remaining gap ${remaining_ss_gap/1e9:.1f}B")
    print(f"  HI: remaining gap ${remaining_hi_gap/1e9:.1f}B")

    del stage1_sim  # Clean up

    # ==========================================================================
    # STAGE 2: Calculate rate increases to close remaining gaps
    # ==========================================================================
    print("\n=== STAGE 2: Calculate rate increases ===")

    # SS: Close remaining gap (negative = deficit needs rate increase)
    if remaining_ss_gap < 0:
        ss_rate_increase = abs(remaining_ss_gap) / oasdi_taxable_payroll
        print(f"  SS: deficit ${remaining_ss_gap/1e9:.1f}B -> rate increase {ss_rate_increase*100:.3f}pp")
    else:
        ss_rate_increase = 0  # Surplus, no increase needed
        print(f"  SS: surplus ${remaining_ss_gap/1e9:.1f}B -> no rate increase")

    # HI: Close remaining gap (can be increase or decrease)
    if remaining_hi_gap < 0:
        hi_rate_increase = abs(remaining_hi_gap) / hi_taxable_payroll
        print(f"  HI: deficit ${remaining_hi_gap/1e9:.1f}B -> rate increase {hi_rate_increase*100:.3f}pp")
    else:
        hi_rate_increase = -remaining_hi_gap / hi_taxable_payroll  # Negative = cut
        print(f"  HI: surplus ${remaining_hi_gap/1e9:.1f}B -> rate cut {abs(hi_rate_increase)*100:.3f}pp")

    new_employee_ss_rate = current_employee_ss_rate + ss_rate_increase / 2
    new_employer_ss_rate = current_employer_ss_rate + ss_rate_increase / 2
    new_employee_hi_rate = current_employee_hi_rate + hi_rate_increase / 2
    new_employer_hi_rate = current_employer_hi_rate + hi_rate_increase / 2

    print(f"New rates: SS {new_employee_ss_rate*2*100:.2f}%, HI {new_employee_hi_rate*2*100:.2f}%")
    print(f"Benefit multiplier: {benefit_multiplier:.4f}")

    # Build reform: rate increases only (no employer tax reform)
    # Option 13 is the "traditional fix" - benefit cuts + rate increases under current law
    reform_dict = {
        # Payroll rate increases to close remaining gaps
        "gov.irs.payroll.social_security.rate.employee": {f"{year}-01-01.{year}-12-31": float(new_employee_ss_rate)},
        "gov.irs.payroll.social_security.rate.employer": {f"{year}-01-01.{year}-12-31": float(new_employer_ss_rate)},
        "gov.irs.payroll.medicare.rate.employee": {f"{year}-01-01.{year}-12-31": float(new_employee_hi_rate)},
        "gov.irs.payroll.medicare.rate.employer": {f"{year}-01-01.{year}-12-31": float(new_employer_hi_rate)},
    }

    reform = Reform.from_dict(reform_dict, country_id="us")

    # Create simulation and apply benefit cut BEFORE any calculate()
    # CRITICAL: Must pass start_instant for the year we're reforming
    print("Running final reform simulation...")
    reform_sim = Microsimulation(reform=reform, dataset=dataset, start_instant=f"{year}-01-01")

    reduced_ss_values = ss_benefits_values * benefit_multiplier
    reform_sim.set_input("social_security", year, reduced_ss_values)

    # Calculate
    reform_income_tax = reform_sim.calculate("income_tax", year).sum()
    reform_tob_oasdi = reform_sim.calculate("tob_revenue_oasdi", year).sum()
    reform_tob_hi = reform_sim.calculate("tob_revenue_medicare_hi", year).sum()
    reform_ss_benefits = reform_sim.calculate("social_security", year).sum()
    reform_employee_ss = reform_sim.calculate("employee_social_security_tax", year).sum()
    reform_employer_ss = reform_sim.calculate("employer_social_security_tax", year).sum()
    reform_employee_hi = reform_sim.calculate("employee_medicare_tax", year).sum()
    reform_employer_hi = reform_sim.calculate("employer_medicare_tax", year).sum()
    reform_additional_medicare = reform_sim.calculate("additional_medicare_tax", year).sum()

    # Calculate rate increase revenue (manual calculation)
    rate_increase_ss_revenue = ss_rate_increase * oasdi_taxable_payroll
    rate_increase_hi_revenue = hi_rate_increase * hi_taxable_payroll
    total_rate_increase_revenue = rate_increase_ss_revenue + rate_increase_hi_revenue

    # New gaps
    reform_ss_income = reform_employee_ss + reform_employer_ss + reform_tob_oasdi
    reform_hi_income = reform_employee_hi + reform_employer_hi + reform_additional_medicare + reform_tob_hi
    new_ss_gap = reform_ss_income - reform_ss_benefits
    new_hi_gap = reform_hi_income - medicare_expenditures

    actual_benefit_cut = ss_benefits - reform_ss_benefits

    print(f"\nResults:")
    print(f"  SS Gap: ${ss_gap/1e9:.1f}B -> ${new_ss_gap/1e9:.1f}B")
    print(f"  HI Gap: ${hi_gap/1e9:.1f}B -> ${new_hi_gap/1e9:.1f}B")
    print(f"  Benefit cut: ${actual_benefit_cut/1e9:.1f}B ({actual_benefit_cut/ss_benefits*100:.1f}%)")
    print(f"  Income tax impact: ${(reform_income_tax - baseline_income_tax)/1e9:+.1f}B")
    print(f"  Rate increase revenue: ${total_rate_increase_revenue/1e9:.1f}B")

    import os
    results = {}

    # Option 13 result
    if not skip_option13:
        option13_result = {
            "year": year,
            "baseline_ss_benefits": float(ss_benefits),
            "baseline_income_tax": float(baseline_income_tax),
            "baseline_ss_gap": float(ss_gap),
            "baseline_hi_gap": float(hi_gap),
            "benefit_multiplier": float(benefit_multiplier),
            "new_employee_ss_rate": float(new_employee_ss_rate),
            "new_employer_ss_rate": float(new_employer_ss_rate),
            "new_employee_hi_rate": float(new_employee_hi_rate),
            "new_employer_hi_rate": float(new_employer_hi_rate),
            "reform_ss_benefits": float(reform_ss_benefits),
            "reform_income_tax": float(reform_income_tax),
            "reform_ss_gap": float(new_ss_gap),
            "reform_hi_gap": float(new_hi_gap),
            "benefit_cut": float(actual_benefit_cut),
            "income_tax_impact": float(reform_income_tax - baseline_income_tax),
            "tob_oasdi_impact": float(reform_tob_oasdi - tob_oasdi),
            "tob_hi_impact": float(reform_tob_hi - tob_hi),
            # Rate increase revenue (manual calculation)
            "rate_increase_ss_revenue": float(rate_increase_ss_revenue),
            "rate_increase_hi_revenue": float(rate_increase_hi_revenue),
            "total_rate_increase_revenue": float(total_rate_increase_revenue),
            # Rate changes in percentage points
            "ss_rate_increase_pp": float(ss_rate_increase * 100),
            "hi_rate_increase_pp": float(hi_rate_increase * 100),
            # TOB losses for tracking
            "tob_oasdi_loss": float(tob_oasdi - reform_tob_oasdi),
            "tob_hi_loss": float(tob_hi - reform_tob_hi),
            # Final gaps (reform gaps = payroll income - outgo, should be ~$0)
            "ss_gap_after": float(new_ss_gap),
            "hi_gap_after": float(new_hi_gap),
            "total_gap_after": float(new_ss_gap + new_hi_gap),
        }

        # Save Option 13 result
        os.makedirs("/results/option13", exist_ok=True)
        df = pd.DataFrame([option13_result])
        df.to_csv(f"/results/option13/{year}_static_results.csv", index=False)
        results_volume.commit()
        results['option13'] = option13_result

    # =========================================================================
    # OPTION 14: Option 12 (Extended Roth-Style Swap) vs Balanced Fix Baseline
    # =========================================================================
    if not skip_option14:
        print(f"\n{'='*60}")
        print(f"OPTION 14 (OPTION 12 vs BALANCED FIX): {year}")
        print(f"{'='*60}")

        # Option 14 = Balanced fix tax increases + Option 12 reforms
        # The baseline for Option 14 is the Option 13 result (balanced fix)
        option12_dict = get_option12_dict()

        # Combine balanced fix tax increases with Option 12 reforms
        # Option 12 reforms override tax rates where they apply
        option14_reform_dict = {**reform_dict}  # Start with balanced fix tax increases
        option14_reform_dict.update(option12_dict)  # Add Option 12 reforms

        option14_reform = Reform.from_dict(option14_reform_dict, country_id="us")

        # CRITICAL: Must pass start_instant for the year we're reforming
        print("Running Option 14 simulation...")
        option14_sim = Microsimulation(reform=option14_reform, dataset=dataset, start_instant=f"{year}-01-01")

        # Apply same benefit cuts as balanced fix
        option14_sim.set_input("social_security", year, reduced_ss_values)

        # Calculate Option 14 results
        option14_income_tax = option14_sim.calculate("income_tax", year).sum()
        option14_tob_oasdi = option14_sim.calculate("tob_revenue_oasdi", year).sum()
        option14_tob_hi = option14_sim.calculate("tob_revenue_medicare_hi", year).sum()
        option14_ss_benefits = option14_sim.calculate("social_security", year).sum()
        option14_employee_ss = option14_sim.calculate("employee_social_security_tax", year).sum()
        option14_employer_ss = option14_sim.calculate("employer_social_security_tax", year).sum()
        option14_employee_hi = option14_sim.calculate("employee_medicare_tax", year).sum()
        option14_employer_hi = option14_sim.calculate("employer_medicare_tax", year).sum()

        # Option 12 specific: employer payroll tax revenue
        # Must use map_to="household" and period=year to properly aggregate tax_unit level variables
        option14_employer_ss_revenue = option14_sim.calculate("employer_ss_tax_income_tax_revenue", map_to="household", period=year).sum()
        option14_employer_hi_revenue = option14_sim.calculate("employer_medicare_tax_income_tax_revenue", map_to="household", period=year).sum()

        # Option 14 impacts (vs balanced fix baseline = Option 13)
        option14_income_tax_impact = option14_income_tax - reform_income_tax
        option14_tob_oasdi_impact = option14_tob_oasdi - reform_tob_oasdi
        option14_tob_hi_impact = option14_tob_hi - reform_tob_hi

        # Trust fund impacts for Option 14
        # Gains: employer payroll taxes now taxable as income
        option14_oasdi_gain = float(option14_employer_ss_revenue)
        option14_hi_gain = float(option14_employer_hi_revenue)
        # Losses: reduced TOB from lower taxable SS (due to phase-out)
        option14_oasdi_loss = float(reform_tob_oasdi - option14_tob_oasdi)
        option14_hi_loss = float(reform_tob_hi - option14_tob_hi)
        option14_oasdi_net = option14_oasdi_gain - option14_oasdi_loss
        option14_hi_net = option14_hi_gain - option14_hi_loss

        print(f"\nOption 14 Results (vs Balanced Fix):")
        print(f"  Income tax impact: ${option14_income_tax_impact/1e9:+.1f}B")
        print(f"  OASDI net impact: ${option14_oasdi_net/1e9:+.1f}B (gain: ${option14_oasdi_gain/1e9:.1f}B, loss: ${option14_oasdi_loss/1e9:.1f}B)")
        print(f"  HI net impact: ${option14_hi_net/1e9:+.1f}B (gain: ${option14_hi_gain/1e9:.1f}B, loss: ${option14_hi_loss/1e9:.1f}B)")

        option14_result = {
            "year": year,
            # Baseline is the balanced fix (Option 13)
            "baseline_income_tax": float(reform_income_tax),
            "baseline_tob_oasdi": float(reform_tob_oasdi),
            "baseline_tob_hi": float(reform_tob_hi),
            # Reform is Option 12 on top of balanced fix
            "reform_income_tax": float(option14_income_tax),
            "reform_tob_oasdi": float(option14_tob_oasdi),
            "reform_tob_hi": float(option14_tob_hi),
            # Impacts
            "income_tax_impact": float(option14_income_tax_impact),
            "tob_oasdi_impact": float(option14_tob_oasdi_impact),
            "tob_hi_impact": float(option14_tob_hi_impact),
            # Trust fund breakdown
            "employer_ss_tax_revenue": float(option14_employer_ss_revenue),
            "employer_hi_tax_revenue": float(option14_employer_hi_revenue),
            "oasdi_gain": option14_oasdi_gain,
            "hi_gain": option14_hi_gain,
            "oasdi_loss": option14_oasdi_loss,
            "hi_loss": option14_hi_loss,
            "oasdi_net_impact": option14_oasdi_net,
            "hi_net_impact": option14_hi_net,
        }

        # Save Option 14 result
        os.makedirs("/results/option14", exist_ok=True)
        df = pd.DataFrame([option14_result])
        df.to_csv(f"/results/option14/{year}_static_results.csv", index=False)
        results_volume.commit()
        results['option14'] = option14_result

    return results


# Backwards compatibility alias for running jobs
compute_option13_year = compute_option13_and_14_year


@app.local_entrypoint()
def main(
    years: str = "2035,2036,2037",
    option13_only: bool = False,
    option14_only: bool = False,
):
    """Run Option 13 and/or Option 14 for specified years.

    Args:
        years: Comma-separated years to compute
        option13_only: Only compute Option 13 (balanced fix baseline)
        option14_only: Only compute Option 14 (requires Option 13 already computed)
    """
    year_list = [int(y.strip()) for y in years.split(",")]

    # Determine what to run
    run_option13 = not option14_only
    run_option14 = not option13_only

    if option13_only and option14_only:
        print("Error: Cannot specify both --option13-only and --option14-only")
        return

    options_str = []
    if run_option13:
        options_str.append("Option 13")
    if run_option14:
        options_str.append("Option 14")
    print(f"Running {' & '.join(options_str)} for years: {year_list}")

    option13_results = []
    option14_results = []

    # Pass flags to the compute function
    args = [(year, not run_option13, not run_option14) for year in year_list]

    for result in compute_option13_and_14_year.starmap(args):
        if result.get('option13'):
            opt13 = result['option13']
            option13_results.append(opt13)
            print(f"\n=== Year {opt13['year']} - Option 13 ===")
            print(f"  SS Gap: ${opt13['baseline_ss_gap']/1e9:.1f}B -> ${opt13['reform_ss_gap']/1e9:.1f}B")
            print(f"  HI Gap: ${opt13['baseline_hi_gap']/1e9:.1f}B -> ${opt13['reform_hi_gap']/1e9:.1f}B")
            print(f"  Benefit cut: {(1-opt13['benefit_multiplier'])*100:.1f}%")

        if result.get('option14'):
            opt14 = result['option14']
            option14_results.append(opt14)
            print(f"\n=== Year {opt14['year']} - Option 14 ===")
            print(f"  Income tax impact: ${opt14['income_tax_impact']/1e9:+.1f}B")
            print(f"  OASDI net: ${opt14['oasdi_net_impact']/1e9:+.1f}B")
            print(f"  HI net: ${opt14['hi_net_impact']/1e9:+.1f}B")

    # Save combined results
    if option13_results:
        df13 = pd.DataFrame(option13_results)
        df13.to_csv("results/option13_results.csv", index=False)
        print(f"\nOption 13 results saved to results/option13_results.csv")

    if option14_results:
        df14 = pd.DataFrame(option14_results)
        df14.to_csv("results/option14_results.csv", index=False)
        print(f"Option 14 results saved to results/option14_results.csv")
