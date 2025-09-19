#!/usr/bin/env python
"""
Generate mock policy impact data for testing purposes.

This creates the same structure as the real data but with placeholder values.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def main():
    print("Generating mock policy impact data...")

    # Fiscal impacts data
    fiscal_data = []
    years = list(range(2026, 2036))

    reforms = [
        ("option1", "Full Repeal of Social Security Benefits Taxation", None),
        ("option2", "Taxation of 85% of Social Security Benefits", None),
        ("option3", "85% Taxation with Permanent Senior Deduction Extension", None),
        ("option4", "Social Security Tax Credit System ($500)", 500),
        ("option5", "Roth-Style Swap", None),
        ("option6", "Phased Roth-Style Swap", None),
        ("option7", "Eliminate Bonus Senior Deduction", None),
    ]

    for reform_id, reform_name, variant in reforms:
        for year in years:
            # Generate mock impact value
            base_impact = np.random.uniform(50, 150)
            year_factor = 1 + (year - 2026) * 0.05
            impact = round(base_impact * year_factor, 1)

            fiscal_data.append({
                'reform_id': reform_id,
                'reform_name': reform_name,
                'variant_value': variant,
                'year': year,
                'impact_billions': impact
            })

    fiscal_df = pd.DataFrame(fiscal_data)

    # Save fiscal impacts
    output_dir = Path('data')
    output_dir.mkdir(exist_ok=True)

    fiscal_output = output_dir / 'policy_impacts.csv'
    fiscal_df.to_csv(fiscal_output, index=False)
    print(f"Fiscal impacts saved to {fiscal_output}")

    # Also save to React dashboard
    dashboard_output = Path('policy-impact-dashboard/public/policy_impacts.csv')
    if dashboard_output.parent.exists():
        fiscal_df.to_csv(dashboard_output, index=False)
        print(f"Also saved to {dashboard_output}")

    # Household impacts data
    household_data = []
    income_points = list(range(0, 200001, 500))

    for reform_id, reform_name, _ in reforms:
        for year in [2026, 2030, 2035]:  # Sample years for mock data
            baseline_base = 40000
            for income in income_points:
                baseline = baseline_base + income * 0.75
                reform_impact = np.random.uniform(-2000, 5000) if income < 50000 else np.random.uniform(-500, 1000)

                household_data.append({
                    'reform': reform_name,
                    'year': year,
                    'employment_income': income,
                    'baseline_net_income': baseline,
                    'reform_net_income': baseline + reform_impact,
                    'change_in_net_income': reform_impact
                })

    household_df = pd.DataFrame(household_data)

    # Save household impacts
    household_output = output_dir / 'household_impacts.csv'
    household_df.to_csv(household_output, index=False)
    print(f"Household impacts saved to {household_output}")

    # Also save to Jupyter Book
    jupyterbook_output = Path('jupyterbook/household_impacts_all_years.csv')
    if jupyterbook_output.parent.exists():
        household_df.to_csv(jupyterbook_output, index=False)
        print(f"Also saved to {jupyterbook_output}")

    print(f"\n✓ Generated {len(fiscal_df)} fiscal impact rows")
    print(f"✓ Generated {len(household_df)} household impact rows")
    print("\nMock data generation complete!")

if __name__ == "__main__":
    main()